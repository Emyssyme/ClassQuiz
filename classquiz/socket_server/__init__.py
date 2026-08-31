# SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)
#
# SPDX-License-Identifier: MPL-2.0


import base64
import hashlib
import json
import os
import random

import socketio
from cryptography.fernet import Fernet

from classquiz.config import redis, settings
from classquiz.db.models import (
    PlayGame,
    QuizQuestionType,
    GameSession,
    GamePlayer,
    VotingQuizAnswer,
    AnswerDataList,
    AnswerData,
)
from pydantic import BaseModel, ValidationError
from datetime import datetime

from classquiz.socket_server.helpers import (
    check_answer,
    check_captcha,
    has_already_answered,
)
from .models import (
    RejoinGameData,
    JoinGameData,
    ReturnQuestion,
    SubmitAnswerData,
    RegisterAsAdminData,
    KickPlayerInput,
    ConnectSessionIdEvent,
    SPGetQuestionData,
    SPSubmitAnswerData,
)

from classquiz.socket_server.export_helpers import save_quiz_to_storage
from classquiz.socket_server.session import get_session, save_session

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])
settings = settings()


def get_fernet_key() -> bytes:
    hlib = hashlib.sha256()
    hlib.update(settings.secret_key.encode("utf-8"))
    return base64.urlsafe_b64encode(hlib.hexdigest().encode("latin-1")[:32])


fernet = Fernet(get_fernet_key())


async def generate_final_results(game_data: PlayGame, game_pin: str) -> dict:
    results = {}
    for i in range(len(game_data.questions)):
        redis_res = await redis.get(f"game_session:{game_pin}:{i}")
        if redis_res is None:
            continue
        else:
            results[str(i)] = json.loads(redis_res)
    return results


def calculate_score(z: float, t: int) -> int:
    t = t * 1000
    res = (t - z) / t
    return int(res * 1000)


async def set_answer(answers, game_pin: str, q_index: int, data: AnswerData) -> AnswerDataList:
    if answers is None:
        answers = AnswerDataList([data])
    else:
        answers = AnswerDataList.model_validate_json(answers)
        answers.append(data)
    await redis.set(
        f"game_session:{game_pin}:{q_index}",
        answers.model_dump_json(),
        ex=7200,
    )
    return answers


@sio.event
async def rejoin_game(sid: str, data: dict):
    redis_res = await redis.get(f"game:{data['game_pin']}")
    if redis_res is None:
        await sio.emit("game_not_found", room=sid)
        return
    try:
        data = RejoinGameData(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
    redis_sid_key = f"game_session:{data.game_pin}:players:{data.username}"
    old_sid = await redis.get(redis_sid_key)
    if old_sid != data.old_sid:
        return
    encrypted_datetime = fernet.encrypt(datetime.now().isoformat().encode("utf-8")).decode("utf-8")
    await sio.emit("time_sync", encrypted_datetime, room=sid)
    await redis.set(redis_sid_key, sid)
    await redis.srem(
        f"game_session:{data.game_pin}:players",
        GamePlayer(username=data.username, sid=data.old_sid).model_dump_json(),
    )
    await redis.sadd(
        f"game_session:{data.game_pin}:players",
        GamePlayer(username=data.username, sid=sid).model_dump_json(),
    )
    game_data = PlayGame.model_validate_json(redis_res)
    session = {
        "game_pin": data.game_pin,
        "username": data.username,
        "sid_custom": sid,
        "admin": False,
    }
    await save_session(sid, sio, session)
    await sio.enter_room(sid, data.game_pin)
    await sio.emit(
        "rejoined_game",
        game_data.to_player_data(),
        room=sid,
    )


@sio.event
async def join_game(sid: str, data: dict):
    redis_res = await redis.get(f"game:{data['game_pin']}")
    if redis_res is None:
        await sio.emit("game_not_found", room=sid)
        return
    try:
        data = JoinGameData(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    game_data = PlayGame.model_validate_json(redis_res)
    # Self-paced games are always "started" — skip the started check
    if not game_data.self_paced and game_data.started:
        await sio.emit("game_already_started", room=sid)
        return
    # +++ START checking captcha +++
    if game_data.captcha_enabled:
        captcha_res = check_captcha(data.captcha)
        if not captcha_res:
            return
    # --- END checking captcha ---
    if await redis.get(f"game_session:{data.game_pin}:players:{data.username}") is not None:
        await sio.emit("username_already_exists", room=sid)
        return

    session = {
        "game_pin": data.game_pin,
        "username": data.username,
        "sid_custom": sid,
        "admin": False,
    }
    await save_session(sid, sio, session)

    if game_data.self_paced:
        # For self-paced: send all question metadata (without correct answers) immediately
        sp_questions = []
        for i, q in enumerate(game_data.questions):
            q_data = q.model_dump()
            if q.type == QuizQuestionType.SLIDE:
                sp_questions.append({"index": i, "type": q.type, "question": q_data["question"], "time": q_data["time"], "image": q_data.get("image"), "answers": q_data["answers"]})
            elif q.type == QuizQuestionType.VOTING:
                sp_questions.append({"index": i, "type": q.type, "question": q_data["question"], "time": q_data["time"], "image": q_data.get("image"), "answers": [{"answer": a["answer"], "color": a.get("color"), "image": a.get("image")} for a in q_data["answers"]]})
            elif q.type == QuizQuestionType.RANGE:
                sp_questions.append({"index": i, "type": q.type, "question": q_data["question"], "time": q_data["time"], "image": q_data.get("image"), "answers": {"min": q_data["answers"]["min"], "max": q_data["answers"]["max"]}})
            elif q.type == QuizQuestionType.ORDER:
                answers_shuffled = [{"answer": a["answer"], "color": a.get("color")} for a in q_data["answers"]]
                random.shuffle(answers_shuffled)
                sp_questions.append({"index": i, "type": q.type, "question": q_data["question"], "time": q_data["time"], "image": q_data.get("image"), "answers": answers_shuffled})
            else:
                # ABCD, TEXT, CHECK — strip "right" from answers
                clean_answers = [{"answer": a["answer"], "color": a.get("color")} for a in q_data["answers"]] if isinstance(q_data["answers"], list) else q_data["answers"]
                sp_questions.append({"index": i, "type": q.type, "question": q_data["question"], "time": q_data["time"], "image": q_data.get("image"), "answers": clean_answers})
        await sio.emit(
            "self_paced_start",
            {
                "title": game_data.title,
                "description": game_data.description,
                "cover_image": game_data.cover_image,
                "background_color": game_data.background_color,
                "background_image": game_data.background_image,
                "game_pin": data.game_pin,
                "game_id": str(game_data.game_id),
                "question_count": len(game_data.questions),
                "questions": sp_questions,
                "timer_enabled": game_data.timer_enabled,
                "deadline": game_data.deadline,
            },
            room=sid,
        )
    else:
        await sio.emit(
            "joined_game",
            game_data.to_player_data(),
            room=sid,
        )

    await redis.set(f"game_session:{data.game_pin}:players:{data.username}", sid, ex=7200)
    await GamePlayer(username=data.username, sid=sid).to_player_stack(data.game_pin)

    if data.custom_field == "":
        data.custom_field = None
    if data.custom_field is not None:
        await redis.hset(
            f"game:{data.game_pin}:players:custom_fields",
            data.username,
            data.custom_field,
        )

    await sio.emit(
        "player_joined",
        {"username": data.username, "sid": sid},
        room=f"admin:{data.game_pin}",
    )
    # +++ Time-Sync +++
    encrypted_datetime = fernet.encrypt(datetime.now().isoformat().encode("utf-8")).decode("utf-8")
    await sio.emit("time_sync", encrypted_datetime, room=sid)
    # --- Time-Sync ---
    await sio.enter_room(sid, data.game_pin)


@sio.event
async def start_game(sid: str, _data: dict):
    session = await get_session(sid, sio)
    if not session["admin"]:
        return
    game_data = await PlayGame.get_from_redis(session["game_pin"])
    game_data.started = True
    await game_data.save(session["game_pin"])
    await redis.delete(f"game_in_lobby:{game_data.user_id.hex}")
    await sio.emit("start_game", room=session["game_pin"])


@sio.event
async def register_as_admin(sid: str, data: dict):
    try:
        data = RegisterAsAdminData(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    game_pin = data.game_pin
    game_id = data.game_id
    if await redis.get(f"game_session:{game_pin}") is not None:
        await sio.emit("already_registered_as_admin", room=sid)
        return
    await GameSession(admin=sid, game_id=game_id, answers=[]).save(game_pin)
    await sio.emit(
        "registered_as_admin",
        {"game_id": game_id, "game": await redis.get(f"game:{game_pin}")},
        room=sid,
    )
    session = {"game_pin": game_pin, "admin": True, "remote": False}
    await save_session(sid, sio, session)
    await sio.enter_room(sid, game_pin)
    await sio.enter_room(sid, f"admin:{data.game_pin}")


@sio.event
async def get_question_results(sid: str, data: dict):
    session = await get_session(sid, sio)
    if not session["admin"]:
        return
    game_pin = session["game_pin"]
    answer_data_list = await AnswerDataList.get_redis_or_empty(game_pin, data["question_number"])
    game_data = await PlayGame.get_from_redis(game_pin)
    game_data.question_show = False
    await game_data.save(game_pin)
    await sio.emit("question_results", answer_data_list.model_dump(), room=game_pin)


@sio.event
async def set_question_number(sid: str, data: str):
    # data is just a number (as a str) of the question
    session = await get_session(sid, sio)
    if not session["admin"]:
        return
    game_pin = session["game_pin"]
    game_data = await PlayGame.get_from_redis(session["game_pin"])
    game_data.current_question = int(float(data))
    game_data.question_show = True
    await game_data.save(session["game_pin"])
    await redis.set(f"game:{session['game_pin']}:current_time", datetime.now().isoformat(), ex=7200)
    temp_return = game_data.model_dump(include={"questions"})["questions"][int(float(data))]
    if game_data.questions[int(float(data))].type == QuizQuestionType.SLIDE:
        await sio.emit(
            "set_question_number",
            {
                "question_index": int(float(data)),
            },
            room=sid,
        )
        return
    if game_data.questions[int(float(data))].type == QuizQuestionType.VOTING:
        for i in range(len(temp_return["answers"])):
            temp_return["answers"][i] = VotingQuizAnswer(**temp_return["answers"][i])
    temp_return["type"] = game_data.questions[int(float(data))].type
    if temp_return["type"] == QuizQuestionType.ORDER:
        random.shuffle(temp_return["answers"])
    await sio.emit(
        "set_question_number",
        {
            "question_index": int(float(data)),
            "question": ReturnQuestion(**temp_return).model_dump(),
        },
        room=game_pin,
    )


@sio.event
async def submit_answer(sid: str, data: dict):
    now = datetime.now()
    try:
        data = SubmitAnswerData(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    data.answer = str(data.answer)
    session = await get_session(sid, sio)
    question_index = int(float(data.question_index))
    game_data = await PlayGame.get_from_redis(session["game_pin"])

    if question_index != game_data.current_question:
        await sio.emit("question_not_active", room=sid)
        return

    already_answered = await has_already_answered(session["game_pin"], question_index, session["username"])
    if already_answered:
        await sio.emit("already_replied", room=sid)
        return

    answer_right, answer = check_answer(game_data, data)
    latency = int(float(session["ping"]))
    time_q_started = datetime.fromisoformat(await redis.get(f"game:{session['game_pin']}:current_time"))
    diff = (time_q_started - now).total_seconds() * 1000  # - timedelta(milliseconds=latency)
    score = 0
    if answer_right:
        score = calculate_score(
            abs(diff) - latency,
            int(float(game_data.questions[question_index].time)),
        )
        if score > 1000:
            score = 1000
    await redis.hincrby(f"game_session:{session['game_pin']}:player_scores", session["username"], score)
    answer_data = AnswerData(
        username=session["username"],
        answer=answer,
        right=answer_right,
        time_taken=abs(diff) - latency,
        score=score,
    )
    answers = await redis.get(f"game_session:{session['game_pin']}:{data.question_index}")
    answers = await set_answer(
        answers,
        game_pin=session["game_pin"],
        data=answer_data,
        q_index=int(float(data.question_index)),
    )
    player_count = await redis.scard(f"game_session:{session['game_pin']}:players")
    await sio.emit("player_answer", {})
    if len(answers) == player_count:
        game_data = await PlayGame.get_from_redis(session["game_pin"])
        game_data.question_show = False
        await game_data.save(session["game_pin"])
        await sio.emit("everyone_answered", {})


@sio.event
async def get_final_results(sid: str, _data: dict):
    session: dict = await get_session(sid, sio)
    if not session["admin"]:
        return
    game_data = await PlayGame.get_from_redis(session["game_pin"])
    results = await generate_final_results(game_data, session["game_pin"])
    await sio.emit("final_results", results, room=session["game_pin"])


@sio.event
async def get_export_token(sid: str):
    session = await get_session(sid, sio)
    if not session["admin"]:
        return
    game_data = await PlayGame.get_from_redis(session["game_pin"])
    results = await generate_final_results(game_data, session["game_pin"])
    token = os.urandom(32).hex()
    await redis.set(f"export_token:{token}", json.dumps(results), ex=7200)
    await sio.emit("export_token", token, room=sid)


@sio.event
async def show_solutions(sid: str, _data: dict):
    session: dict = await get_session(sid, sio)
    game_data = await PlayGame.get_from_redis(session["game_pin"])
    if not session["admin"]:
        return
    await sio.emit(
        "solutions",
        game_data.questions[game_data.current_question].model_dump(),
        room=session["game_pin"],
    )


@sio.event
async def echo_time_sync(sid: str, data: str):
    then_dec = fernet.decrypt(data).decode("utf-8")
    then = datetime.fromisoformat(then_dec)
    now = datetime.now()
    delta = now - then
    session = await get_session(sid, sio)
    session["ping"] = delta.microseconds / 1000
    await save_session(sid, sio, session)


@sio.event
async def kick_player(sid: str, data: dict):
    try:
        data = KickPlayerInput(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return

    session: dict = await get_session(sid, sio)
    if not session["admin"]:
        return

    player_sid = await redis.get(f"game_session:{session['game_pin']}:players:{data.username}")
    await redis.srem(
        f"game_session:{session['game_pin']}:players",
        GamePlayer(username=data.username, sid=player_sid).model_dump_json(),
    )
    await sio.leave_room(player_sid, session["game_pin"])
    await sio.emit("kick", room=player_sid)


class _RegisterAsRemoteInput(BaseModel):
    game_pin: str
    game_id: str


@sio.event
async def register_as_remote(sid: str, data: dict):
    try:
        data = _RegisterAsRemoteInput(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    await sio.emit(
        "registered_as_admin",
        {"game_id": data.game_id, "game": await redis.get(f"game:{data.game_pin}")},
        room=sid,
    )
    await sio.emit("control_visibility", {"visible": False}, room=f"admin:{data.game_pin}")
    session = await get_session(sid, sio)
    session["game_pin"] = data.game_pin
    session["admin"] = True
    session["remote"] = True
    await save_session(sid, sio, session)
    await sio.enter_room(sid, data.game_pin)
    await sio.enter_room(sid, f"admin:{data.game_pin}")


class _SetControlVisibilityInput(BaseModel):
    visible: bool


@sio.event
async def set_control_visibility(sid: str, data: dict):
    try:
        data = _SetControlVisibilityInput(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    session: dict = await get_session(sid, sio)
    await sio.emit(
        "control_visibility",
        {"visible": data.visible},
        room=f"admin:{session['game_pin']}",
    )


# ============================================================
# Self-Paced (Assign) events
# ============================================================


@sio.event
async def sp_get_question(sid: str, data: dict):
    """Self-paced: player requests a specific question by index."""
    try:
        data = SPGetQuestionData(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    session = await get_session(sid, sio)
    game_data = await PlayGame.get_from_redis(session["game_pin"])
    if not game_data.self_paced:
        await sio.emit("error", room=sid)
        return
    q_index = data.question_index
    if q_index < 0 or q_index >= len(game_data.questions):
        await sio.emit("error", room=sid)
        return
    # Record the time the player started this question (for scoring)
    await redis.set(
        f"game_session:{session['game_pin']}:sp:{session['username']}:current_time",
        datetime.now().isoformat(),
        ex=7200,
    )
    await redis.set(
        f"game_session:{session['game_pin']}:sp:{session['username']}:current_q",
        str(q_index),
        ex=7200,
    )
    await sio.emit("sp_question_ready", {"question_index": q_index}, room=sid)


@sio.event
async def sp_submit_answer(sid: str, data: dict):
    """Self-paced: player submits an answer. Gets immediate feedback."""
    now = datetime.now()
    try:
        data = SPSubmitAnswerData(**data)
    except ValidationError as e:
        await sio.emit("error", room=sid)
        print(e)
        return
    data.answer = str(data.answer)
    session = await get_session(sid, sio)
    game_pin = session["game_pin"]
    game_data = await PlayGame.get_from_redis(game_pin)
    if not game_data.self_paced:
        await sio.emit("error", room=sid)
        return
    question_index = int(float(data.question_index))
    if question_index < 0 or question_index >= len(game_data.questions):
        await sio.emit("error", room=sid)
        return

    # Check if already answered this question
    already_answered = await has_already_answered(game_pin, question_index, session["username"])
    if already_answered:
        await sio.emit("already_replied", room=sid)
        return

    # Build a SubmitAnswerData-compatible object for check_answer
    submit_data = SubmitAnswerData(
        question_index=data.question_index,
        answer=data.answer,
        complex_answer=data.complex_answer,
    )
    answer_right, answer = check_answer(game_data, submit_data)

    # Calculate score using individual timer
    score = 0
    if game_data.timer_enabled:
        time_key = f"game_session:{game_pin}:sp:{session['username']}:current_time"
        time_q_started_str = await redis.get(time_key)
        if time_q_started_str:
            time_q_started = datetime.fromisoformat(time_q_started_str)
            diff = (time_q_started - now).total_seconds() * 1000
            latency = int(float(session.get("ping", 0)))
            if answer_right:
                score = calculate_score(
                    abs(diff) - latency,
                    int(float(game_data.questions[question_index].time)),
                )
                if score > 1000:
                    score = 1000
    else:
        # No timer — fixed score for correct answers
        if answer_right:
            score = 1000

    await redis.hincrby(f"game_session:{game_pin}:player_scores", session["username"], score)
    answer_data = AnswerData(
        username=session["username"],
        answer=answer,
        right=answer_right,
        time_taken=0,
        score=score,
    )
    answers = await redis.get(f"game_session:{game_pin}:{data.question_index}")
    await set_answer(
        answers,
        game_pin=game_pin,
        data=answer_data,
        q_index=question_index,
    )

    # Build correct answer for immediate feedback
    q = game_data.questions[question_index]
    correct_answer = None
    if q.type == QuizQuestionType.ABCD or q.type == QuizQuestionType.CHECK:
        correct_answer = [a.model_dump() for a in q.answers if a.right]
    elif q.type == QuizQuestionType.RANGE:
        correct_answer = {"min_correct": q.answers.min_correct, "max_correct": q.answers.max_correct}
    elif q.type == QuizQuestionType.TEXT:
        correct_answer = [a.model_dump() for a in q.answers]
    elif q.type == QuizQuestionType.ORDER:
        correct_answer = [a.model_dump() for a in q.answers]

    await sio.emit(
        "sp_answer_result",
        {
            "question_index": question_index,
            "right": answer_right,
            "score": score,
            "correct_answer": correct_answer,
        },
        room=sid,
    )


@sio.event
async def sp_get_leaderboard(sid: str, _data: dict):
    """Self-paced: player requests the current leaderboard."""
    session = await get_session(sid, sio)
    game_pin = session["game_pin"]
    scores_raw = await redis.hgetall(f"game_session:{game_pin}:player_scores")
    all_scores = []
    for username, sc in scores_raw.items():
        all_scores.append({"username": username, "score": int(sc)})
    all_scores.sort(key=lambda x: x["score"], reverse=True)

    # Find current player's rank
    my_rank = -1
    my_score = 0
    for i, entry in enumerate(all_scores):
        if entry["username"] == session["username"]:
            my_rank = i + 1
            my_score = entry["score"]
            break

    await sio.emit(
        "sp_leaderboard",
        {
            "top": all_scores[:5],
            "my_rank": my_rank,
            "my_score": my_score,
            "total_players": len(all_scores),
        },
        room=sid,
    )


@sio.event
async def sp_finish(sid: str, _data: dict):
    """Self-paced: player has finished all questions."""
    session = await get_session(sid, sio)
    game_pin = session["game_pin"]
    # Mark player as finished
    await redis.sadd(f"game_session:{game_pin}:sp:finished", session["username"])
    # Return full leaderboard
    scores_raw = await redis.hgetall(f"game_session:{game_pin}:player_scores")
    all_scores = []
    for username, sc in scores_raw.items():
        all_scores.append({"username": username, "score": int(sc)})
    all_scores.sort(key=lambda x: x["score"], reverse=True)
    my_rank = -1
    my_score = 0
    for i, entry in enumerate(all_scores):
        if entry["username"] == session["username"]:
            my_rank = i + 1
            my_score = entry["score"]
            break
    await sio.emit(
        "sp_final_results",
        {
            "leaderboard": all_scores,
            "my_rank": my_rank,
            "my_score": my_score,
            "total_players": len(all_scores),
        },
        room=sid,
    )


@sio.event
async def save_quiz(sid: str):
    session: dict = await get_session(sid, sio)
    if not session["admin"]:
        return
    await save_quiz_to_storage(session["game_pin"])
    await sio.emit("results_saved_successfully")


@sio.event
async def connect(sid: str, _environ, _auth):
    session_id = os.urandom(16).hex()
    print("Connection opened with handler")
    sio_session = {"session_id": session_id}
    await sio.save_session(sid, sio_session)
    await sio.emit("session_id", ConnectSessionIdEvent(session_id=session_id).dict())
