"""Servicio de logica de negocio para Rooms."""
from datetime import datetime
import random
import string

from bson import ObjectId

from src.DB.motor import db_instance
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


class RoomError(ValueError):
    """Error controlado de Room con codigo HTTP sugerido."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class RoomService:
    """Servicio centralizado para operaciones de Room."""

    @staticmethod
    def _object_id(room_id: str) -> ObjectId:
        try:
            return ObjectId(room_id)
        except Exception:
            raise RoomError(f"ID de room invalido: {room_id}", status_code=400)

    @staticmethod
    async def _get_room_or_fail(room_id: str) -> dict:
        room = await db_instance.db.rooms.find_one({"_id": RoomService._object_id(room_id)})
        if not room:
            raise RoomError("Room no encontrada", status_code=404)
        return room

    @staticmethod
    async def _get_room_by_code_or_fail(room_code: str) -> dict:
        room = await db_instance.db.rooms.find_one({"room_code": room_code.upper().strip()})
        if not room:
            raise RoomError("Room no encontrada", status_code=404)
        return room

    @staticmethod
    async def _generate_unique_room_code() -> str:
        """Genera un codigo unico de 5 caracteres para la room."""
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            existing = await db_instance.db.rooms.find_one({"room_code": code})
            if not existing:
                return code

    @staticmethod
    def _serialize_room(room: dict) -> dict:
        serialized = dict(room)
        serialized["_id"] = str(serialized["_id"])
        return serialized

    @staticmethod
    def _ensure_owner(room: dict, owner_email: str, message: str) -> None:
        if room.get("owner_email") != owner_email:
            raise RoomError(message, status_code=403)

    @staticmethod
    def _ensure_public_or_owner(room: dict, requester_email: str, message: str) -> None:
        if not room.get("is_public", False) and requester_email != room.get("owner_email"):
            raise RoomError(message, status_code=403)

    @staticmethod
    def _visible_sessions_filter(room: dict, requester_email: str) -> dict:
        if requester_email == room.get("owner_email"):
            return {}
        return {"visible": {"$ne": False}}

    @staticmethod
    def _ensure_session_visible_for_requester(session: dict, room: dict, requester_email: str) -> None:
        if session.get("visible", True) is False and requester_email != room.get("owner_email"):
            raise RoomError("Session no encontrada", status_code=404)

    @staticmethod
    async def create_room(payload: CreateRoomRequest) -> dict:
        """Crea una room con el usuario dueno."""
        room_code = await RoomService._generate_unique_room_code()

        room_doc = {
            "name": payload.name,
            "owner_email": payload.owner_email,
            "room_code": room_code,
            "is_public": payload.is_public,
            "allow_download": payload.allow_download,
            "created_at": datetime.utcnow(),
            "members": [payload.owner_email],
            "waitlist": [],
        }

        result = await db_instance.db.rooms.insert_one(room_doc)
        room_doc["_id"] = str(result.inserted_id)

        return {
            "room_id": str(result.inserted_id),
            "room_code": room_code,
            "room": room_doc,
        }

    @staticmethod
    async def get_user_rooms(owner_email: str) -> dict:
        """Recupera todas las rooms creadas por un usuario."""
        owner_email = owner_email.strip().lower()
        if not owner_email:
            raise RoomError("owner_email es requerido", status_code=400)

        cursor = db_instance.db.rooms.find({"owner_email": owner_email})
        rooms = await cursor.to_list(length=None)
        serialized_rooms = [RoomService._serialize_room(room) for room in rooms]

        return {
            "owner_email": owner_email,
            "total": len(serialized_rooms),
            "rooms": serialized_rooms,
        }

    @staticmethod
    async def join_room(room_id: str, payload: JoinRoomRequest) -> dict:
        """Agrega un usuario como miembro de una room."""
        room = await RoomService._get_room_or_fail(room_id)
        members = room.get("members", [])

        if payload.user_email not in members:
            await db_instance.db.rooms.update_one(
                {"_id": room["_id"]},
                {"$push": {"members": payload.user_email}},
            )
            members.append(payload.user_email)

        return {
            "room_id": room_id,
            "joined": True,
            "members": members,
        }

    @staticmethod
    async def join_room_by_code(payload: JoinRoomByCodeRequest) -> dict:
        """Agrega un usuario como miembro de una room usando room_code."""
        room = await RoomService._get_room_by_code_or_fail(payload.room_code)
        room_id = str(room["_id"])
        members = room.get("members", [])
        waitlist = room.get("waitlist", [])

        if payload.user_email not in members:
            await db_instance.db.rooms.update_one(
                {"_id": room["_id"]},
                {
                    "$addToSet": {"members": payload.user_email},
                    "$pull": {"waitlist": payload.user_email},
                },
            )
            members.append(payload.user_email)
        elif payload.user_email in waitlist:
            await db_instance.db.rooms.update_one(
                {"_id": room["_id"]},
                {"$pull": {"waitlist": payload.user_email}},
            )

        return {
            "room_id": room_id,
            "room_code": room.get("room_code"),
            "room_name": room.get("name"),
            "joined": True,
            "members": members,
            "was_in_waitlist": payload.user_email in waitlist,
        }

    @staticmethod
    async def get_room_session(room_id: str, session_id: str, requester_email: str) -> dict:
        """Retorna datos de una session si el acceso esta permitido."""
        room = await RoomService._get_room_or_fail(room_id)

        session = await db_instance.db.sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session or session.get("room_id") != room_id:
            raise RoomError("Session no encontrada", status_code=404)

        requester_email = requester_email.strip().lower()
        RoomService._ensure_public_or_owner(room, requester_email, "Acceso denegado: session privada")
        RoomService._ensure_session_visible_for_requester(session, room, requester_email)

        return {
            "room": room["name"],
            "session": session,
        }

    @staticmethod
    async def list_room_sessions(room_id: str, requester_email: str) -> dict:
        """Lista todas las sessions de una room con filtro de acceso."""
        room = await RoomService._get_room_or_fail(room_id)

        requester_email = requester_email.strip().lower()
        RoomService._ensure_public_or_owner(room, requester_email, "Acceso denegado: room privada")

        session_filter = {
            "room_id": room_id,
            **RoomService._visible_sessions_filter(room, requester_email),
        }

        cursor = db_instance.db.sessions.find(session_filter, {"_id": 0})
        sessions = await cursor.to_list(length=100)

        return {
            "room": room_id,
            "sessions": sessions,
        }

    @staticmethod
    async def update_room_name(room_id: str, payload: UpdateRoomNameRequest) -> dict:
        """Actualiza el nombre de una room."""
        room = await RoomService._get_room_or_fail(room_id)
        RoomService._ensure_owner(
            room,
            payload.owner_email,
            "Solo el propietario puede actualizar el nombre de la room",
        )

        await db_instance.db.rooms.update_one(
            {"_id": room["_id"]},
            {"$set": {"name": payload.new_name}},
        )

        return {
            "room_id": room_id,
            "message": "Nombre actualizado correctamente",
            "new_name": payload.new_name,
        }

    @staticmethod
    async def add_to_waitlist(room_id: str, payload: WaitlistRequest) -> dict:
        """Agrega un usuario a la lista de espera de una room."""
        room = await RoomService._get_room_or_fail(room_id)

        if payload.user_email in room.get("members", []):
            return {
                "room_id": room_id,
                "message": "El usuario ya es miembro de esta room",
            }

        if payload.user_email in room.get("waitlist", []):
            return {
                "room_id": room_id,
                "message": "El usuario ya esta en la lista de espera",
            }

        await db_instance.db.rooms.update_one(
            {"_id": room["_id"]},
            {"$push": {"waitlist": payload.user_email}},
        )

        return {
            "room_id": room_id,
            "user_email": payload.user_email,
            "message": "Suscrito a la lista de espera correctamente",
            "waitlist_position": len(room.get("waitlist", [])) + 1,
        }

    @staticmethod
    async def get_waitlist(room_id: str, payload: GetWaitlistRequest) -> dict:
        """Retorna la lista de espera de una room."""
        room = await RoomService._get_room_or_fail(room_id)
        RoomService._ensure_owner(
            room,
            payload.owner_email,
            "Solo el propietario puede ver la lista de espera",
        )

        waitlist = room.get("waitlist", [])
        return {
            "room_id": room_id,
            "room_name": room.get("name"),
            "total": len(waitlist),
            "waitlist": waitlist,
        }

    @staticmethod
    async def accept_waitlist_member(room_id: str, payload: AcceptWaitlistMemberRequest) -> dict:
        """Mueve un usuario de waitlist a members."""
        room = await RoomService._get_room_or_fail(room_id)
        RoomService._ensure_owner(
            room,
            payload.owner_email,
            "Solo el propietario puede aceptar usuarios de la lista de espera",
        )

        waitlist = room.get("waitlist", [])
        members = room.get("members", [])

        if payload.user_email in members:
            await db_instance.db.rooms.update_one(
                {"_id": room["_id"]},
                {"$pull": {"waitlist": payload.user_email}},
            )
            return {
                "room_id": room_id,
                "user_email": payload.user_email,
                "accepted": False,
                "message": "El usuario ya era miembro de esta room",
                "members": members,
                "waitlist": [email for email in waitlist if email != payload.user_email],
            }

        if payload.user_email not in waitlist:
            raise RoomError("El usuario no esta en la lista de espera", status_code=404)

        await db_instance.db.rooms.update_one(
            {"_id": room["_id"]},
            {
                "$addToSet": {"members": payload.user_email},
                "$pull": {"waitlist": payload.user_email},
            },
        )

        members.append(payload.user_email)
        updated_waitlist = [email for email in waitlist if email != payload.user_email]

        return {
            "room_id": room_id,
            "user_email": payload.user_email,
            "accepted": True,
            "message": "Usuario aceptado correctamente",
            "members": members,
            "waitlist": updated_waitlist,
        }

    @staticmethod
    async def accept_all_waitlist(room_id: str, payload: AcceptAllWaitlistRequest) -> dict:
        """Mueve todos los usuarios de waitlist a members."""
        room = await RoomService._get_room_or_fail(room_id)
        RoomService._ensure_owner(
            room,
            payload.owner_email,
            "Solo el propietario puede aceptar usuarios de la lista de espera",
        )

        waitlist = room.get("waitlist", [])
        members = room.get("members", [])
        accepted_members = [email for email in waitlist if email not in members]

        if waitlist:
            await db_instance.db.rooms.update_one(
                {"_id": room["_id"]},
                {
                    "$addToSet": {"members": {"$each": waitlist}},
                    "$set": {"waitlist": []},
                },
            )

        return {
            "room_id": room_id,
            "accepted_count": len(accepted_members),
            "accepted_members": accepted_members,
            "members": members + accepted_members,
            "waitlist": [],
            "message": "Lista de espera aceptada correctamente",
        }

    @staticmethod
    async def delete_room(room_id: str, payload: DeleteRoomRequest) -> dict:
        """Elimina una room y sus sesiones."""
        room = await RoomService._get_room_or_fail(room_id)
        RoomService._ensure_owner(
            room,
            payload.owner_email,
            "Solo el propietario puede eliminar la room",
        )

        await db_instance.db.sessions.delete_many({"room_id": room_id})
        result = await db_instance.db.rooms.delete_one({"_id": room["_id"]})

        return {
            "room_id": room_id,
            "message": "Room eliminada correctamente",
            "deleted_count": result.deleted_count,
        }
