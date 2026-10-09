from datetime import timedelta
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from open_garage_erp.config import Settings
from open_garage_erp.database import build_session_factory, session_dependency
from open_garage_erp.models import Customer, RepairOrder, SessionToken, User, Vehicle, utc_now
from open_garage_erp.schemas import (
    MAX_SQLITE_INTEGER,
    CustomerCreate,
    CustomerResponse,
    LoginRequest,
    LoginResponse,
    RepairOrderCreate,
    RepairOrderResponse,
    RepairOrderStatus,
    RepairOrderStatusUpdate,
    VehicleCreate,
    VehicleResponse,
)
from open_garage_erp.security import (
    DUMMY_PASSWORD_HASH,
    generate_session_token,
    hash_session_token,
    verify_password,
)

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "cancelled"},
    "approved": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class RepairOrderNotFound(Exception):
    pass


class InvalidStatusTransition(Exception):
    def __init__(self, current_status: str, target_status: str) -> None:
        self.current_status = current_status
        self.target_status = target_status


def transition_repair_order_status(
    session: Session, order_id: int, target_status: str
) -> RepairOrder:
    allowed_sources = [
        current_status
        for current_status, targets in VALID_STATUS_TRANSITIONS.items()
        if target_status in targets
    ]
    statement = (
        update(RepairOrder)
        .where(RepairOrder.id == order_id, RepairOrder.status.in_(allowed_sources))
        .values(status=target_status, updated_at=utc_now())
        .returning(RepairOrder)
    )
    order = session.scalar(statement)
    if order is None:
        session.expire_all()
        current_order = session.get(RepairOrder, order_id, populate_existing=True)
        if current_order is None:
            raise RepairOrderNotFound
        raise InvalidStatusTransition(current_order.status, target_status)
    session.commit()
    session.refresh(order)
    return order


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.ensure_local_database_directory()
    session_factory = build_session_factory(settings.database_url)
    get_session = session_dependency(session_factory)
    SessionDep = Annotated[Session, Depends(get_session)]
    EntityId = Annotated[int, Path(gt=0, le=MAX_SQLITE_INTEGER)]
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.state.database_url = settings.database_url

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            body = exc.detail
        else:
            code = "not_found" if exc.status_code == 404 else "http_error"
            body = error_body(code, str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @app.exception_handler(IntegrityError)
    async def integrity_error(_request: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_body("integrity_conflict", "The request conflicts with existing data"),
        )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def landing() -> str:
        return """<!doctype html><html><head><title>Open Garage ERP</title></head>
        <body><main><h1>Open Garage ERP</h1><p>Automotive repair shop API.</p>
        <p><a href=\"/docs\">Interactive API documentation</a></p></main></body></html>"""

    @app.post("/api/auth/login", response_model=LoginResponse, tags=["authentication"])
    def login(payload: LoginRequest, session: SessionDep):
        user = session.scalar(
            select(User).where(User.shop_id == payload.shop_id, User.email == payload.email)
        )
        password_hash = (
            user.password_hash if user is not None and user.is_active else DUMMY_PASSWORD_HASH
        )
        password_matches = verify_password(payload.password, password_hash)
        if user is None or not user.is_active or not password_matches:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_body("invalid_credentials", "Invalid shop, email, or password"),
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = generate_session_token()
        expires_at = utc_now() + timedelta(hours=12)
        session.add(
            SessionToken(
                user_id=user.id,
                token_hash=hash_session_token(access_token),
                expires_at=expires_at,
            )
        )
        session.commit()
        return LoginResponse(access_token=access_token, expires_at=expires_at)

    @app.post(
        "/api/auth/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        tags=["authentication"],
    )
    def logout(session: SessionDep, authorization: Annotated[str | None, Header()] = None):
        scheme, _, token = (authorization or "").partition(" ")
        stored_token = None
        if scheme.casefold() == "bearer" and token:
            stored_token = session.scalar(
                select(SessionToken).where(
                    SessionToken.token_hash == hash_session_token(token),
                    SessionToken.revoked_at.is_(None),
                    SessionToken.expires_at > utc_now(),
                )
            )
        if stored_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_body("invalid_session", "Session token is invalid or expired"),
                headers={"WWW-Authenticate": "Bearer"},
            )
        stored_token.revoked_at = utc_now()
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/customers",
        response_model=CustomerResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["customers"],
    )
    def create_customer(payload: CustomerCreate, session: SessionDep):
        customer = Customer(**payload.model_dump())
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return customer

    @app.get("/api/customers", response_model=list[CustomerResponse], tags=["customers"])
    def list_customers(session: SessionDep):
        return session.scalars(select(Customer).order_by(Customer.id)).all()

    @app.get("/api/customers/{customer_id}", response_model=CustomerResponse, tags=["customers"])
    def get_customer(customer_id: EntityId, session: SessionDep):
        customer = session.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(
                status_code=404,
                detail=error_body("not_found", f"Customer {customer_id} not found"),
            )
        return customer

    @app.post(
        "/api/vehicles",
        response_model=VehicleResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["vehicles"],
    )
    def create_vehicle(payload: VehicleCreate, session: SessionDep):
        if session.get(Customer, payload.customer_id) is None:
            raise HTTPException(
                status_code=404,
                detail=error_body("not_found", f"Customer {payload.customer_id} not found"),
            )
        vehicle = Vehicle(**payload.model_dump())
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        return vehicle

    @app.get("/api/vehicles", response_model=list[VehicleResponse], tags=["vehicles"])
    def list_vehicles(session: SessionDep):
        return session.scalars(select(Vehicle).order_by(Vehicle.id)).all()

    @app.get("/api/vehicles/{vehicle_id}", response_model=VehicleResponse, tags=["vehicles"])
    def get_vehicle(vehicle_id: EntityId, session: SessionDep):
        vehicle = session.get(Vehicle, vehicle_id)
        if vehicle is None:
            raise HTTPException(
                status_code=404,
                detail=error_body("not_found", f"Vehicle {vehicle_id} not found"),
            )
        return vehicle

    @app.post(
        "/api/repair-orders",
        response_model=RepairOrderResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["repair orders"],
    )
    def create_repair_order(payload: RepairOrderCreate, session: SessionDep):
        if session.get(Vehicle, payload.vehicle_id) is None:
            raise HTTPException(
                status_code=404,
                detail=error_body("not_found", f"Vehicle {payload.vehicle_id} not found"),
            )
        order = RepairOrder(**payload.model_dump(), status=RepairOrderStatus.DRAFT.value)
        session.add(order)
        session.commit()
        session.refresh(order)
        return order

    @app.get("/api/repair-orders", response_model=list[RepairOrderResponse], tags=["repair orders"])
    def list_repair_orders(session: SessionDep):
        return session.scalars(select(RepairOrder).order_by(RepairOrder.id)).all()

    @app.get(
        "/api/repair-orders/{order_id}", response_model=RepairOrderResponse, tags=["repair orders"]
    )
    def get_repair_order(order_id: EntityId, session: SessionDep):
        order = session.get(RepairOrder, order_id)
        if order is None:
            raise HTTPException(
                status_code=404,
                detail=error_body("not_found", f"Repair order {order_id} not found"),
            )
        return order

    @app.patch(
        "/api/repair-orders/{order_id}/status",
        response_model=RepairOrderResponse,
        tags=["repair orders"],
    )
    def update_repair_order_status(
        order_id: EntityId, payload: RepairOrderStatusUpdate, session: SessionDep
    ):
        target = payload.status.value
        try:
            return transition_repair_order_status(session, order_id, target)
        except RepairOrderNotFound:
            raise HTTPException(
                status_code=404,
                detail=error_body("not_found", f"Repair order {order_id} not found"),
            ) from None
        except InvalidStatusTransition as exc:
            raise HTTPException(
                status_code=409,
                detail=error_body(
                    "invalid_status_transition",
                    f"Cannot transition repair order from {exc.current_status} to {target}",
                    {"from": exc.current_status, "to": target},
                ),
            ) from None

    @app.get("/api/dashboard/summary", tags=["dashboard"])
    def dashboard_summary(session: SessionDep) -> dict[str, int]:
        open_statuses = ["draft", "approved", "in_progress"]
        return {
            "customers": session.scalar(select(func.count(Customer.id))) or 0,
            "vehicles": session.scalar(select(func.count(Vehicle.id))) or 0,
            "repair_orders": session.scalar(select(func.count(RepairOrder.id))) or 0,
            "open_repair_orders": session.scalar(
                select(func.count(RepairOrder.id)).where(RepairOrder.status.in_(open_statuses))
            )
            or 0,
            "estimate_total_cents": sum(session.scalars(select(RepairOrder.estimate_cents))),
        }

    return app
