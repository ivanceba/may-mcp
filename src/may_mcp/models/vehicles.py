"""Vehicle fields accepted by May 0.44.2's public REST API."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VehicleType = Literal["car", "van", "motorbike", "scooter"]
Name = Annotated[str, Field(min_length=1, max_length=100)]
ShortText = Annotated[str, Field(max_length=50)]
FuelType = Annotated[str, Field(max_length=20)]
Capacity = Annotated[float, Field(allow_inf_nan=False)]


class VehicleFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    make: ShortText | None = None
    model: ShortText | None = None
    year: int | None = None
    registration: Annotated[str, Field(max_length=20)] | None = None
    vin: ShortText | None = None
    fuel_type: FuelType | None = None
    tank_capacity: Capacity | None = None


class VehicleCreate(VehicleFields):
    """Omitted optional fields retain May's defaults; null clears nullable fields."""

    name: Name
    vehicle_type: VehicleType


class VehicleUpdate(VehicleFields):
    """Only supplied fields change. Name, type, and active status cannot be null."""

    name: Name | None = None
    vehicle_type: VehicleType | None = None
    is_active: bool | None = None

    @field_validator("name", "vehicle_type", "is_active", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        return self
