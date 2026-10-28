from typing import Optional
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class UserGroupBase(SQLModel):
    name: str
    description: str

class UserGroup(UserGroupBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    usergroup_uuid: str = ""
    creation_date: str = ""
    update_date: str = ""

class UserGroupCreate(UserGroupBase):
    org_id: int = Field(default=None, foreign_key="organization.id")
    pass

class UserGroupUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None

class UserGroupRead(UserGroupBase):
    id: int
    org_id: int = Field(default=None, foreign_key="organization.id")
    usergroup_uuid: str
    creation_date: str
    update_date: str
    pass


class UserGroupContact(SQLModel):
    """Mailing projection for one group member. No other user fields."""

    user_uuid: str
    email: str
    first_name: str


class UserGroupContactsPage(SQLModel):
    items: list[UserGroupContact]
    total: int
    page: int
    limit: int


class UserGroupResolve(SQLModel):
    """One group id for a contacts token. No member fields."""

    id: int
    name: str
