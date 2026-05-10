"""Pydantic base config for API schemas.

Per CONVENTIONS.md §4:
- DB uses snake_case, API wire uses camelCase — conversion in this layer, not per field
- from_attributes=True so routes can do ArticleRead.model_validate(article_orm) directly
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class APIModel(BaseModel):
    """Base for all request/response schemas."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
