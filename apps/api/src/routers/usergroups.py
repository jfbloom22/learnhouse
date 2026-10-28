from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.usergroups import (
    UserGroupContactsPage,
    UserGroupCreate,
    UserGroupRead,
    UserGroupResolve,
    UserGroupUpdate,
)
from src.db.users import PublicUser, UserReadPublic
from src.services.users.usergroups import (
    add_resources_to_usergroup,
    add_users_to_usergroup,
    create_usergroup,
    delete_usergroup_by_id,
    get_resources_by_usergroup,
    get_usergroup_contacts,
    get_usergroups_by_resource,
    resolve_usergroup_for_contacts,
    get_users_linked_to_usergroup,
    read_usergroup_by_id,
    read_usergroups_by_org_id,
    remove_resources_from_usergroup,
    remove_users_from_usergroup,
    update_usergroup_by_id,
)
from src.security.auth import get_current_user
from src.core.events.database import get_db_session


router = APIRouter()


@router.post(
    "/",
    response_model=UserGroupRead,
    tags=["usergroups"],
    summary="Create a usergroup",
    description="Create a new usergroup within an organization. Requires admin/maintainer permissions on the organization.",
    responses={
        200: {"description": "Usergroup created successfully.", "model": UserGroupRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to create usergroups"},
        404: {"description": "Organization not found"},
    },
)
async def api_create_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_object: UserGroupCreate,
) -> UserGroupRead:
    """
    Create User
    """
    return await create_usergroup(request, db_session, current_user, usergroup_object)


@router.get(
    "/resolve",
    response_model=UserGroupResolve,
    tags=["usergroups"],
    summary="Resolve one usergroup name for the contacts token",
    description=(
        "Exact name match inside the token's organization. "
        "Requires usergroups.action_read_contacts. "
        "Zero matches is 404. More than one match is 409."
    ),
    responses={
        200: {"description": "The single matching group.", "model": UserGroupResolve},
        400: {"description": "Name is blank"},
        403: {"description": "Token lacks action_read_contacts"},
        404: {"description": "No group with that name in the token org"},
        409: {"description": "More than one group with that name"},
    },
)
async def api_resolve_usergroup_for_contacts(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    name: str = Query(min_length=1),
) -> UserGroupResolve:
    return await resolve_usergroup_for_contacts(request, db_session, current_user, name)


@router.get(
    "/{usergroup_id}",
    response_model=UserGroupRead,
    tags=["usergroups"],
    summary="Get a usergroup",
    description="Retrieve a usergroup by its numeric identifier.",
    responses={
        200: {"description": "Usergroup retrieved.", "model": UserGroupRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this usergroup"},
        404: {"description": "Usergroup not found"},
    },
)
async def api_get_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
) -> UserGroupRead:
    """
    Get UserGroup
    """
    return await read_usergroup_by_id(request, db_session, current_user, usergroup_id)


@router.get(
    "/{usergroup_id}/users",
    response_model=list[UserReadPublic],
    tags=["usergroups"],
    summary="List users in a usergroup",
    description="Retrieve the list of users that belong to a specific usergroup. Sensitive fields (is_superadmin, signup_method) are excluded.",
    responses={
        200: {"description": "Users linked to the usergroup.", "model": list[UserReadPublic]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view usergroup members"},
        404: {"description": "Usergroup not found"},
    },
)
async def api_get_users_linked_to_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
) -> list[UserReadPublic]:
    """
    Get Users linked to UserGroup
    """
    return await get_users_linked_to_usergroup(
        request, db_session, current_user, usergroup_id
    )


@router.get(
    "/{usergroup_id}/contacts",
    response_model=UserGroupContactsPage,
    tags=["usergroups"],
    summary="List mailing contacts for a usergroup",
    description=(
        "Page user_uuid, email, and first_name for one usergroup. "
        "Requires an API token with usergroups.action_read_contacts in that org. "
        "usergroups.action_read does not grant this route."
    ),
    responses={
        200: {"description": "One page of contacts.", "model": UserGroupContactsPage},
        401: {"description": "Authentication required"},
        403: {"description": "Token lacks action_read_contacts or is outside the org"},
        404: {"description": "Usergroup not found"},
    },
)
async def api_get_usergroup_contacts(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
) -> UserGroupContactsPage:
    return await get_usergroup_contacts(
        request,
        db_session,
        current_user,
        usergroup_id,
        page=page,
        limit=limit,
    )


@router.get(
    "/org/{org_id}",
    response_model=list[UserGroupRead],
    tags=["usergroups"],
    summary="List usergroups for an organization",
    description="Retrieve every usergroup that belongs to a given organization.",
    responses={
        200: {"description": "Usergroups for the organization.", "model": list[UserGroupRead]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view usergroups for this organization"},
        404: {"description": "Organization not found"},
    },
)
async def api_get_usergroups(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    org_id: int,
) -> list[UserGroupRead]:
    """
    Get UserGroups by Org
    """
    return await read_usergroups_by_org_id(request, db_session, current_user, org_id)


@router.get(
    "/{usergroup_id}/resources",
    response_model=list[str],
    tags=["usergroups"],
    summary="List resources linked to a usergroup",
    description="Return the UUIDs of resources (courses, folders, etc.) that are linked to a usergroup.",
    responses={
        200: {"description": "Resource UUIDs linked to the usergroup.", "model": list[str]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this usergroup"},
        404: {"description": "Usergroup not found"},
    },
)
async def api_get_resources_linked_to_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
) -> list[str]:
    """
    Get resource UUIDs linked to a UserGroup
    """
    return await get_resources_by_usergroup(
        request, db_session, current_user, usergroup_id
    )


@router.get(
    "/resource/{resource_uuid}",
    response_model=list[UserGroupRead],
    tags=["usergroups"],
    summary="List usergroups linked to a resource",
    description="Retrieve every usergroup that is linked to a given resource UUID.",
    responses={
        200: {"description": "Usergroups linked to the resource.", "model": list[UserGroupRead]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view usergroups for this resource"},
        404: {"description": "Resource not found"},
    },
)
async def api_get_usergroupsby_resource(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    resource_uuid: str,
) -> list[UserGroupRead]:
    """
    Get UserGroups by Org
    """
    return await get_usergroups_by_resource(
        request, db_session, current_user, resource_uuid
    )


@router.put(
    "/{usergroup_id}",
    response_model=UserGroupRead,
    tags=["usergroups"],
    summary="Update a usergroup",
    description="Update the name, description, or other attributes of a usergroup.",
    responses={
        200: {"description": "Usergroup updated successfully.", "model": UserGroupRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to update this usergroup"},
        404: {"description": "Usergroup not found"},
    },
)
async def api_update_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
    usergroup_object: UserGroupUpdate,
) -> UserGroupRead:
    """
    Update UserGroup
    """
    return await update_usergroup_by_id(
        request, db_session, current_user, usergroup_id, usergroup_object
    )


@router.delete(
    "/{usergroup_id}",
    tags=["usergroups"],
    summary="Delete a usergroup",
    description="Permanently delete a usergroup along with its user and resource links.",
    responses={
        200: {"description": "Usergroup deleted successfully."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to delete this usergroup"},
        404: {"description": "Usergroup not found"},
    },
)
async def api_delete_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
) -> str:
    """
    Delete UserGroup
    """
    return await delete_usergroup_by_id(request, db_session, current_user, usergroup_id)


@router.post(
    "/{usergroup_id}/add_users",
    tags=["usergroups"],
    summary="Add users to a usergroup",
    description="Add one or more users to a usergroup. User IDs should be provided as a comma-separated string.",
    responses={
        200: {"description": "Users added to the usergroup."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to modify this usergroup"},
        404: {"description": "Usergroup or user not found"},
    },
)
async def api_add_users_to_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
    user_ids: str,
) -> str:
    """
    Add Users to UserGroup
    """
    # Validate the comma-separated id list before it reaches the service, which
    # does int(uid) unconditionally and would otherwise raise an unhandled 500
    # on any non-numeric (or empty) input.
    parts = [uid.strip() for uid in user_ids.split(",")]
    if not all(part.isdigit() for part in parts):
        raise HTTPException(
            status_code=422,
            detail="user_ids must be a comma-separated list of integer user IDs",
        )
    return await add_users_to_usergroup(
        request, db_session, current_user, usergroup_id, user_ids
    )


@router.delete(
    "/{usergroup_id}/remove_users",
    tags=["usergroups"],
    summary="Remove users from a usergroup",
    description="Remove one or more users from a usergroup. User IDs should be provided as a comma-separated string.",
    responses={
        200: {"description": "Users removed from the usergroup."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to modify this usergroup"},
        404: {"description": "Usergroup or user not found"},
    },
)
async def api_delete_users_from_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
    user_ids: str,
) -> str:
    """
    Delete Users from UserGroup
    """
    # Validate before the service does int(uid) on each part, which would
    # otherwise raise an unhandled 500 on non-numeric / empty input.
    parts = [uid.strip() for uid in user_ids.split(",")]
    if not all(part.isdigit() for part in parts):
        raise HTTPException(
            status_code=422,
            detail="user_ids must be a comma-separated list of integer user IDs",
        )
    return await remove_users_from_usergroup(
        request, db_session, current_user, usergroup_id, user_ids
    )


@router.post(
    "/{usergroup_id}/add_resources",
    tags=["usergroups"],
    summary="Add resources to a usergroup",
    description="Link one or more resources (courses, folders, etc.) to a usergroup. Resource UUIDs should be provided as a comma-separated string.",
    responses={
        200: {"description": "Resources linked to the usergroup."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to modify this usergroup"},
        404: {"description": "Usergroup or resource not found"},
    },
)
async def api_add_resources_to_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
    resource_uuids: str,
) -> str:
    """
    Add Resources to UserGroup
    """
    return await add_resources_to_usergroup(
        request, db_session, current_user, usergroup_id, resource_uuids
    )


@router.delete(
    "/{usergroup_id}/remove_resources",
    tags=["usergroups"],
    summary="Remove resources from a usergroup",
    description="Unlink one or more resources from a usergroup. Resource UUIDs should be provided as a comma-separated string.",
    responses={
        200: {"description": "Resources unlinked from the usergroup."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to modify this usergroup"},
        404: {"description": "Usergroup or resource not found"},
    },
)
async def api_delete_resources_from_usergroup(
    *,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
    usergroup_id: int,
    resource_uuids: str,
) -> str:
    """
    Delete Resources from UserGroup
    """
    return await remove_resources_from_usergroup(
        request, db_session, current_user, usergroup_id, resource_uuids
    )
