"""Contacts route: email stays behind usergroups.action_read_contacts."""

from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.usergroup_user import UserGroupUser
from src.db.usergroups import UserGroup
from src.db.users import APITokenUser, PublicUser, User
from src.routers.usergroups import router as usergroups_router
from src.security.auth import get_current_user
from src.services.api_tokens.api_tokens import validate_rights_structure
from src.services.users.usergroups import (
    get_usergroup_contacts,
    get_users_linked_to_usergroup,
    resolve_usergroup_for_contacts,
)


def _token(org_id: int, **usergroup_rights) -> APITokenUser:
    return APITokenUser(
        id=1,
        user_uuid="apitoken_contacts",
        username="api_token",
        org_id=org_id,
        rights={"usergroups": usergroup_rights},
        token_name="Contacts test",
        created_by_user_id=1,
    )


def _token_rights(**usergroup_flags) -> dict:
    empty = {
        "action_create": False,
        "action_read": False,
        "action_update": False,
        "action_delete": False,
    }
    rights = {
        key: dict(empty)
        for key in (
            "courses",
            "activities",
            "coursechapters",
            "folders",
            "media",
            "certifications",
            "usergroups",
            "payments",
        )
    }
    rights["search"] = {"action_read": False}
    rights["usergroups"].update(usergroup_flags)
    return rights


async def _add_user(db, user_id: int, email: str, first_name: str, uuid: str) -> User:
    user = User(
        id=user_id,
        username=f"user{user_id}",
        first_name=first_name,
        last_name="Member",
        email=email,
        password="hashed",
        user_uuid=uuid,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _add_group(db, org_id: int, name: str, uuid: str, users: list[User]) -> UserGroup:
    group = UserGroup(
        org_id=org_id,
        name=name,
        description="",
        usergroup_uuid=uuid,
        creation_date="2024-01-01",
        update_date="2024-01-01",
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    for user in users:
        db.add(
            UserGroupUser(
                usergroup_id=group.id,
                user_id=user.id,
                org_id=org_id,
                creation_date="2024-01-01",
                update_date="2024-01-01",
            )
        )
    await db.commit()
    return group


class TestUsergroupContacts:
    async def test_action_read_is_forbidden_and_users_list_has_no_email(
        self, db, org, mock_request, regular_user
    ):
        member = await _add_user(db, 3, "member@test.com", "Member", "user_member")
        group = await _add_group(db, org.id, "cohort-proof", "usergroup_proof", [member])
        reader = _token(org.id, action_read=True, action_read_contacts=False)

        with pytest.raises(HTTPException) as exc:
            await get_usergroup_contacts(mock_request, db, reader, group.id)
        assert exc.value.status_code == 403

        listed = await get_users_linked_to_usergroup(mock_request, db, reader, group.id)
        dumped = [user.model_dump() for user in listed]
        assert dumped[0]["user_uuid"] == "user_member"
        assert all("email" not in row for row in dumped)

        app = FastAPI()
        app.include_router(usergroups_router, prefix="/api/v1/usergroups")
        app.dependency_overrides[get_db_session] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: reader
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/usergroups/{group.id}/users")
        assert response.status_code == 200
        assert "email" not in response.json()[0]
        del regular_user

    async def test_contacts_right_returns_email_for_that_group_only(
        self, db, org, mock_request
    ):
        in_group = await _add_user(db, 3, "in@test.com", "In", "user_in")
        outsider = await _add_user(db, 4, "out@test.com", "Out", "user_out")
        blank_name = await _add_user(db, 5, "blank@test.com", "", "user_blank")
        group = await _add_group(
            db, org.id, "cohort-proof", "usergroup_proof", [in_group, blank_name]
        )
        await _add_group(db, org.id, "other", "usergroup_other", [outsider])
        token = _token(org.id, action_read=False, action_read_contacts=True)

        first = await get_usergroup_contacts(mock_request, db, token, group.id, page=1, limit=1)
        second = await get_usergroup_contacts(mock_request, db, token, group.id, page=2, limit=1)

        assert first.total == 2
        assert second.total == 2
        rows = [item.model_dump() for item in first.items + second.items]
        assert rows == [
            {"user_uuid": "user_in", "email": "in@test.com", "first_name": "In"},
            {"user_uuid": "user_blank", "email": "blank@test.com", "first_name": ""},
        ]
        assert all(set(row) == {"user_uuid", "email", "first_name"} for row in rows)

    async def test_token_for_another_org_is_forbidden(self, db, org, other_org, mock_request):
        member = await _add_user(db, 3, "member@test.com", "Member", "user_member")
        group = await _add_group(db, org.id, "cohort-proof", "usergroup_proof", [member])
        foreign = _token(other_org.id, action_read_contacts=True)

        with pytest.raises(HTTPException) as exc:
            await get_usergroup_contacts(mock_request, db, foreign, group.id)
        assert exc.value.status_code == 403
        assert "outside its organization" in exc.value.detail

    async def test_session_user_cannot_read_contacts(self, db, org, mock_request, admin_user):
        member = await _add_user(db, 3, "member@test.com", "Member", "user_member")
        group = await _add_group(db, org.id, "cohort-proof", "usergroup_proof", [member])
        assert isinstance(admin_user, PublicUser)
        with pytest.raises(HTTPException) as exc:
            await get_usergroup_contacts(mock_request, db, admin_user, group.id)
        assert exc.value.status_code == 403

    async def test_group_manager_can_mint_contacts_right_and_reader_cannot(self):
        await validate_rights_structure(
            _token_rights(action_read_contacts=True),
            {"usergroups": {"action_read": True, "action_update": True}},
        )
        with pytest.raises(HTTPException) as exc:
            await validate_rights_structure(
                _token_rights(action_read_contacts=True),
                {"usergroups": {"action_read": True, "action_update": False}},
            )
        assert exc.value.status_code == 403
        assert "action_read_contacts" in exc.value.detail

    async def test_resolve_name_is_one_group_in_the_token_org(self, db, org, other_org, mock_request):
        member = await _add_user(db, 3, "member@test.com", "Member", "user_member")
        group = await _add_group(db, org.id, "cohort-proof", "usergroup_proof", [member])
        await _add_group(db, other_org.id, "cohort-proof", "usergroup_other_proof", [member])
        token = _token(org.id, action_read_contacts=True)
        resolved = await resolve_usergroup_for_contacts(mock_request, db, token, "cohort-proof")
        assert resolved.id == group.id
        assert resolved.model_dump() == {"id": group.id, "name": "cohort-proof"}

        await _add_group(db, org.id, "cohort-proof", "usergroup_proof_dup", [member])
        with pytest.raises(HTTPException) as duplicate:
            await resolve_usergroup_for_contacts(mock_request, db, token, "cohort-proof")
        assert duplicate.value.status_code == 409

        reader = _token(org.id, action_read=True)
        with pytest.raises(HTTPException) as forbidden:
            await resolve_usergroup_for_contacts(mock_request, db, reader, "cohort-proof")
        assert forbidden.value.status_code == 403
