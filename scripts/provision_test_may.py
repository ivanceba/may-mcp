"""Provision synthetic records inside the disposable test container only."""

import json
import os
from pathlib import Path


def main():
    if (
        os.environ.get("MAY_MCP_TEST_INSTANCE") != "1"
        or os.environ.get("DATABASE_URL") != "sqlite:////app/data/may.db"
    ):
        raise SystemExit("Provisioning requires the isolated May test container.")

    from app import create_app, db
    from app.models import User, Vehicle
    from config import APP_VERSION

    if APP_VERSION != "0.44.2":
        raise SystemExit("Unexpected May version in test container.")

    app = create_app()
    with app.app_context():
        if User.query.filter_by(username="mcp-test").first():
            raise SystemExit("Test data already exists; recreate the disposable container.")
        user = User(username="mcp-test", email="mcp-test@example.invalid", currency="EUR")
        user.set_password("synthetic-unused-password")
        api_key = user.generate_api_key()
        db.session.add(user)
        db.session.flush()
        other = User(username="mcp-other", email="mcp-other@example.invalid", currency="EUR")
        other.set_password("synthetic-unused-password")
        other_api_key = other.generate_api_key()
        db.session.add(other)
        db.session.flush()
        vehicle = Vehicle(owner_id=user.id, name="MCP synthetic vehicle", vehicle_type="car")
        other.shared_vehicles.append(vehicle)
        private_vehicle = Vehicle(
            owner_id=other.id, name="Other synthetic vehicle", vehicle_type="van"
        )
        db.session.add_all([vehicle, private_vehicle])
        db.session.commit()
        path = Path("/app/data/mcp-test.json")
        with path.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "api_key": api_key,
                    "other_api_key": other_api_key,
                    "vehicle_id": vehicle.id,
                    "other_vehicle_id": private_vehicle.id,
                },
                stream,
            )
        path.chmod(0o600)
    print("Synthetic May accounts and vehicles provisioned.")


if __name__ == "__main__":
    main()
