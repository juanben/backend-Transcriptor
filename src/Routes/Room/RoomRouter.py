from fastapi import APIRouter, HTTPException, Query
from pydantic import EmailStr

from src.Routes.Room.RoomModels import (
    AcceptAllWaitlistRequest,
    AcceptWaitlistMemberRequest,
    CreateRoomRequest,
    DeleteRoomRequest,
    GetWaitlistRequest,
    JoinRoomByCodeRequest,
    JoinRoomRequest,
    UpdateRoomNameRequest,
    WaitlistRequest,
)
from src.Routes.Room.RoomService import RoomError, RoomService

router = APIRouter(prefix="/room", tags=["Room"])


def handle_room_error(error: RoomError):
    """Convierte errores controlados del servicio en respuestas HTTP."""
    raise HTTPException(status_code=error.status_code, detail=str(error))


@router.post("/createRoom")
async def create_room(payload: CreateRoomRequest):
    """Crea una room con el usuario dueno."""
    try:
        return await RoomService.create_room(payload)
    except RoomError as error:
        handle_room_error(error)


@router.get("/user-rooms/{owner_email}")
async def get_user_rooms(owner_email: str):
    """Recupera todas las rooms creadas por un usuario."""
    try:
        return await RoomService.get_user_rooms(owner_email)
    except RoomError as error:
        handle_room_error(error)


@router.post("/{room_id}/join")
async def join_room(room_id: str, payload: JoinRoomRequest):
    """Un usuario se une a una room."""
    try:
        return await RoomService.join_room(room_id, payload)
    except RoomError as error:
        handle_room_error(error)


@router.post("/join-by-code")
async def join_room_by_code(payload: JoinRoomByCodeRequest):
    """Un usuario se une a una room usando room_code."""
    try:
        return await RoomService.join_room_by_code(payload)
    except RoomError as error:
        handle_room_error(error)


@router.get("/{room_id}/session/{session_id}")
async def get_room_session(room_id: str, session_id: str, requester_email: str):
    """Retorna datos de la session si el acceso esta permitido."""
    try:
        return await RoomService.get_room_session(room_id, session_id, requester_email)
    except RoomError as error:
        handle_room_error(error)


@router.get("/{room_id}/sessions")
async def list_room_sessions(room_id: str, requester_email: str):
    """Lista todas las sessions de una room con filtro de acceso."""
    try:
        return await RoomService.list_room_sessions(room_id, requester_email)
    except RoomError as error:
        handle_room_error(error)


@router.put("/{room_id}/update-name")
async def update_room_name(room_id: str, payload: UpdateRoomNameRequest):
    """Actualiza el nombre de una room."""
    try:
        return await RoomService.update_room_name(room_id, payload)
    except RoomError as error:
        handle_room_error(error)


@router.post("/{room_id}/waitlist")
async def add_to_waitlist(room_id: str, payload: WaitlistRequest):
    """Agrega un usuario a la lista de espera de una room."""
    try:
        return await RoomService.add_to_waitlist(room_id, payload)
    except RoomError as error:
        handle_room_error(error)


@router.get("/{room_id}/waitlist")
async def get_waitlist(room_id: str, owner_email: EmailStr = Query(...)):
    """Obtiene la lista de espera de una room."""
    try:
        payload = GetWaitlistRequest(owner_email=owner_email)
        return await RoomService.get_waitlist(room_id, payload)
    except RoomError as error:
        handle_room_error(error)


@router.post("/{room_id}/waitlist/accept")
async def accept_waitlist_member(room_id: str, payload: AcceptWaitlistMemberRequest):
    """Acepta un usuario de la lista de espera."""
    try:
        return await RoomService.accept_waitlist_member(room_id, payload)
    except RoomError as error:
        handle_room_error(error)


@router.post("/{room_id}/waitlist/accept-all")
async def accept_all_waitlist(room_id: str, payload: AcceptAllWaitlistRequest):
    """Acepta todos los usuarios de la lista de espera."""
    try:
        return await RoomService.accept_all_waitlist(room_id, payload)
    except RoomError as error:
        handle_room_error(error)


@router.delete("/{room_id}")
async def delete_room(room_id: str, payload: DeleteRoomRequest):
    """Elimina una room."""
    try:
        return await RoomService.delete_room(room_id, payload)
    except RoomError as error:
        handle_room_error(error)

