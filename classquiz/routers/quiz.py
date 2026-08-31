# SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)
#
# SPDX-License-Identifier: MPL-2.0


import json
import random
import re
import uuid
from datetime import datetime, timezone
from random import randint

import ormar.exceptions

from classquiz.helpers import generate_spreadsheet, handle_import_from_excel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError, BaseModel

from classquiz.auth import get_current_user
from classquiz.config import redis, settings, storage, meilisearch
from classquiz.db.models import Quiz, User, PlayGame, GameInLobby, QuizQuestion, QuizQuestionType
from classquiz.helpers.box_controller import generate_code
from classquiz.kahoot_importer.import_quiz import import_quiz
import urllib.parse

settings = settings()

router = APIRouter()


@router.get("/get/{quiz_id}")
async def get_quiz_from_id(quiz_id: str, user: User | None = Depends(get_current_user)):
    try:
        quiz_id = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="badly formed quiz id")
    if user is None:
        quiz = await Quiz.objects.get_or_none(id=quiz_id, public=True)
    else:
        quiz = await Quiz.objects.get_or_none(id=quiz_id, user_id=user.id)
    if quiz is None:
        public_quiz = await Quiz.objects.get_or_none(id=quiz_id, public=True)
        if public_quiz is None:
            return JSONResponse(status_code=404, content={"detail": "quiz not found"})
        else:
            return public_quiz
    else:
        return quiz


class PublicQuizResponseUser(BaseModel):
    username: str
    id: uuid.UUID


class PublicQuizResponse(Quiz.get_pydantic(exclude={"questions"})):
    user_id: PublicQuizResponseUser
    questions: list[QuizQuestion]
    likes: int
    dislikes: int
    views: int
    plays: int


@router.get("/get/public/{quiz_id}")
async def get_public_quiz(quiz_id: uuid.UUID):
    quiz = await Quiz.objects.select_related("user_id").get_or_none(id=quiz_id)
    if quiz is None:
        return JSONResponse(status_code=404, content={"detail": "quiz not found"})
    else:
        quiz.views += 1
        await quiz.update()
        return PublicQuizResponse(**quiz.model_dump())


@router.post("/start/{quiz_id}")
async def start_quiz(
    quiz_id: str,
    game_mode: str,
    captcha_enabled: bool = True,
    custom_field: str | None = None,
    cqcs_enabled: bool = False,
    randomize_answers: bool = False,
    user: User = Depends(get_current_user),
):
    try:
        quiz_id = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="badly formed quiz id")
    quiz = await Quiz.objects.get_or_none(id=quiz_id, user_id=user.id)
    if quiz is None:
        quiz = await Quiz.objects.get_or_none(id=quiz_id, public=True)
        if quiz is None:
            return JSONResponse(status_code=404, content={"detail": "quiz not found"})
    quiz.plays += 1
    await quiz.update()
    game_pin = randint(100000, 999999)
    if custom_field == "":
        custom_field = None
    game = await redis.get(f"game:{game_pin}")
    while game is not None:
        game_pin = randint(100000, 999999)
        game = await redis.get(f"game:{game_pin}")

    if randomize_answers:
        for question in quiz.questions:
            if question["type"] == QuizQuestionType.RANGE:
                continue
            if question["type"] == QuizQuestionType.SLIDE:
                continue
            random.shuffle(question["answers"])

    game = PlayGame(
        quiz_id=quiz_id,
        game_pin=str(game_pin),
        questions=quiz.questions,
        game_id=uuid.uuid4(),
        title=quiz.title,
        description=quiz.description,
        captcha_enabled=captcha_enabled,
        cover_image=quiz.cover_image,
        game_mode=game_mode,
        user_id=user.id,
        background_color=quiz.background_color,
        custom_field=custom_field,
        background_image=quiz.background_image,
    )
    code = None
    if cqcs_enabled:
        code = generate_code(6)
        await redis.set(f"game:cqc:code:{code}", game_pin, ex=3600)
    await redis.set(f"game:{str(game.game_pin)}", game.model_dump_json(), ex=18000)
    await redis.set(f"game_pin:{user.id}:{quiz_id}", game_pin, ex=18000)

    await redis.set(
        f"game_in_lobby:{user.id.hex}",
        GameInLobby(game_id=game.game_id, game_pin=str(game_pin), quiz_title=quiz.title).model_dump_json(),
        ex=900,
    )
    return {**quiz.model_dump(exclude={"id"}), **game.model_dump(exclude={"questions"}), "cqc_code": code}


@router.post("/assign/{quiz_id}")
async def assign_quiz(
    quiz_id: str,
    deadline: str,
    timer_enabled: bool = True,
    captcha_enabled: bool = False,
    custom_field: str | None = None,
    randomize_answers: bool = False,
    user: User = Depends(get_current_user),
):
    """Create a self-paced (assign) game. Players can join and play at their own pace until the deadline."""
    try:
        quiz_id = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="badly formed quiz id")
    quiz = await Quiz.objects.get_or_none(id=quiz_id, user_id=user.id)
    if quiz is None:
        quiz = await Quiz.objects.get_or_none(id=quiz_id, public=True)
        if quiz is None:
            return JSONResponse(status_code=404, content={"detail": "quiz not found"})

    # Parse deadline and calculate TTL
    try:
        deadline_dt = datetime.fromisoformat(deadline)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid deadline format, use ISO 8601")
    ttl_seconds = int((deadline_dt - datetime.now(timezone.utc)).total_seconds())
    if ttl_seconds <= 0:
        raise HTTPException(status_code=400, detail="deadline must be in the future")
    # Cap TTL at 30 days
    ttl_seconds = min(ttl_seconds, 30 * 24 * 3600)

    quiz.plays += 1
    await quiz.update()
    game_pin = randint(100000, 999999)
    if custom_field == "":
        custom_field = None
    game = await redis.get(f"game:{game_pin}")
    while game is not None:
        game_pin = randint(100000, 999999)
        game = await redis.get(f"game:{game_pin}")

    if randomize_answers:
        for question in quiz.questions:
            if question["type"] == QuizQuestionType.RANGE:
                continue
            if question["type"] == QuizQuestionType.SLIDE:
                continue
            random.shuffle(question["answers"])

    game = PlayGame(
        quiz_id=quiz_id,
        game_pin=str(game_pin),
        questions=quiz.questions,
        game_id=uuid.uuid4(),
        title=quiz.title,
        description=quiz.description,
        captcha_enabled=captcha_enabled,
        cover_image=quiz.cover_image,
        game_mode="self_paced",
        user_id=user.id,
        background_color=quiz.background_color,
        custom_field=custom_field,
        background_image=quiz.background_image,
        self_paced=True,
        started=True,  # Self-paced games are always "started"
        deadline=deadline,
        timer_enabled=timer_enabled,
    )
    await redis.set(f"game:{str(game.game_pin)}", game.model_dump_json(), ex=ttl_seconds)
    await redis.set(f"game_pin:{user.id}:{quiz_id}", game_pin, ex=ttl_seconds)
    await redis.sadd(f"user_assignments:{user.id}", str(game_pin))

    return {
        "game_pin": str(game_pin),
        "game_id": str(game.game_id),
        "deadline": deadline,
        "title": quiz.title,
        "quiz_id": str(quiz_id),
    }


@router.get("/assign/list")
async def list_user_assignments(user: User = Depends(get_current_user)):
    """List all active assignments created by the current user."""
    pins = await redis.smembers(f"user_assignments:{user.id}")
    assignments = []
    for pin in pins:
        game_raw = await redis.get(f"game:{pin}")
        if game_raw is None:
            await redis.srem(f"user_assignments:{user.id}", pin)
            continue
        try:
            game_data = PlayGame.model_validate_json(game_raw)
        except Exception:
            continue

        total_players = await redis.scard(f"game_session:{pin}:players")
        finished_players = await redis.scard(f"game_session:{pin}:sp:finished")

        assignments.append({
            "game_pin": pin,
            "game_id": str(game_data.game_id),
            "quiz_id": str(game_data.quiz_id),
            "title": game_data.title,
            "description": game_data.description,
            "cover_image": game_data.cover_image,
            "deadline": game_data.deadline,
            "timer_enabled": game_data.timer_enabled,
            "question_count": len(game_data.questions),
            "total_players": total_players,
            "finished_players": finished_players,
        })
    assignments.sort(key=lambda x: x["deadline"] or "")
    return assignments


@router.get("/assign/{game_pin}/status")
async def get_assign_status(game_pin: str, user: User = Depends(get_current_user)):
    """Get real-time status of a self-paced assignment including intermediate results for the admin dashboard."""
    redis_res = await redis.get(f"game:{game_pin}")
    if redis_res is None:
        raise HTTPException(status_code=404, detail="assignment not found")
    game_data = PlayGame.model_validate_json(redis_res)
    if game_data.user_id != user.id:
        raise HTTPException(status_code=403, detail="not your assignment")
    if not game_data.self_paced:
        raise HTTPException(status_code=400, detail="this is not a self-paced game")

    # Get players
    players_raw = await redis.smembers(f"game_session:{game_pin}:players")
    players = []
    for p in players_raw:
        try:
            players.append(json.loads(p))
        except Exception:
            pass

    # Get scores
    scores_raw = await redis.hgetall(f"game_session:{game_pin}:player_scores")
    scores = {}
    for username, sc in scores_raw.items():
        scores[username] = int(sc)

    # Get finished players
    finished_raw = await redis.smembers(f"game_session:{game_pin}:sp:finished")
    finished = list(finished_raw) if finished_raw else []

    # Get detailed answers per question
    questions_summary = []
    question_stats = []
    answers_by_q = {}

    for i, q in enumerate(game_data.questions):
        questions_summary.append({
            "index": i,
            "question": q.question,
            "type": q.type,
            "time": q.time,
            "image": q.image,
        })

        raw_ans = await redis.get(f"game_session:{game_pin}:{i}")
        ans_list = []
        if raw_ans:
            try:
                ans_list = json.loads(raw_ans)
            except Exception:
                ans_list = []
        answers_by_q[i] = ans_list

        correct_count = sum(1 for a in ans_list if a.get("right"))
        wrong_count = len(ans_list) - correct_count
        accuracy = round((correct_count / len(ans_list) * 100)) if ans_list else 0

        question_stats.append({
            "index": i,
            "question": q.question,
            "type": q.type,
            "total_answered": len(ans_list),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "accuracy": accuracy,
            "answers": ans_list,
        })

    # Build per-player status with intermediate answers matrix
    player_status = []
    for p in players:
        username = p["username"]
        current_q = await redis.get(f"game_session:{game_pin}:sp:{username}:current_q")

        player_answers = {}
        for i in range(len(game_data.questions)):
            for a in answers_by_q.get(i, []):
                if a.get("username") == username:
                    player_answers[str(i)] = {
                        "right": a.get("right"),
                        "answer": a.get("answer"),
                        "score": a.get("score"),
                    }
                    break

        player_status.append({
            "username": username,
            "score": scores.get(username, 0),
            "current_question": int(current_q) if current_q else 0,
            "finished": username in finished,
            "answers": player_answers,
        })
    player_status.sort(key=lambda x: x["score"], reverse=True)

    return {
        "game_pin": game_pin,
        "game_id": str(game_data.game_id),
        "quiz_id": str(game_data.quiz_id),
        "title": game_data.title,
        "description": game_data.description,
        "deadline": game_data.deadline,
        "timer_enabled": game_data.timer_enabled,
        "question_count": len(game_data.questions),
        "total_players": len(players),
        "finished_count": len(finished),
        "questions": questions_summary,
        "question_stats": question_stats,
        "players": player_status,
    }


@router.post("/assign/{game_pin}/save")
async def save_assign_results(game_pin: str, user: User = Depends(get_current_user)):
    """Save assignment results to permanent GameResults storage."""
    redis_res = await redis.get(f"game:{game_pin}")
    if redis_res is None:
        raise HTTPException(status_code=404, detail="assignment not found")
    game_data = PlayGame.model_validate_json(redis_res)
    if game_data.user_id != user.id:
        raise HTTPException(status_code=403, detail="not your assignment")

    from classquiz.socket_server.export_helpers import save_quiz_to_storage

    await save_quiz_to_storage(game_pin)
    return {"status": "saved"}


@router.delete("/assign/{game_pin}")
async def delete_assignment(game_pin: str, user: User = Depends(get_current_user)):
    """Delete an assignment and remove from active list."""
    redis_res = await redis.get(f"game:{game_pin}")
    if redis_res is not None:
        game_data = PlayGame.model_validate_json(redis_res)
        if game_data.user_id != user.id:
            raise HTTPException(status_code=403, detail="not your assignment")
        await redis.delete(f"game:{game_pin}")
    await redis.srem(f"user_assignments:{user.id}", game_pin)
    return {"status": "deleted"}


class CheckIfCaptchaEnabledResponse(BaseModel):
    enabled: bool
    game_mode: str | None = None
    custom_field: str | None = None


@router.get("/play/check_captcha/{game_pin}", response_model=CheckIfCaptchaEnabledResponse)
async def check_if_captcha_enabled(game_pin: str):
    game = await redis.get(f"game:{game_pin}")
    if game is None:
        return JSONResponse(status_code=404, content={"detail": "game not found"})
    game = PlayGame.model_validate_json(game)
    if game.captcha_enabled:
        return CheckIfCaptchaEnabledResponse(enabled=True, game_mode=game.game_mode, custom_field=game.custom_field)
    else:
        return CheckIfCaptchaEnabledResponse(enabled=False, game_mode=game.game_mode, custom_field=game.custom_field)


@router.get("/join/{game_pin}", deprecated=True)
async def get_game_id(game_pin: str):
    redis_res = await redis.get(f"game:{game_pin}")
    if redis_res is None:
        raise HTTPException(status_code=404, detail="game not found")
    else:
        return json.loads(redis_res)["game_id"]


@router.get("/list")
async def get_quiz_list(user: User = Depends(get_current_user), page_size: int | None = 10, page: int | None = 1):
    try:
        return (
            await Quiz.objects.order_by(Quiz.updated_at.desc())
            .filter(user_id=user.id)
            .paginate(page, page_size=page_size)
            .all()
        )
    except ormar.exceptions.QueryDefinitionError:
        raise HTTPException(status_code=400, detail="Invalid page(size). page(size) have to be greater than 0.")


@router.post("/import/{quiz_id}")
async def import_quiz_route(quiz_id: str, user: User = Depends(get_current_user)):
    if user.storage_used > settings.free_storage_limit:
        raise HTTPException(status_code=409, detail="Storage limit reached")
    resp_data = await import_quiz(quiz_id, user)
    try:
        if type(resp_data) is int:
            raise HTTPException(status_code=resp_data, detail="kahoot")
        else:
            return resp_data
    except ValidationError:
        raise HTTPException(400, detail="unsupported")


@router.delete("/delete/{quiz_id}")
async def delete_quiz(quiz_id: str, user: User = Depends(get_current_user)):
    try:
        quiz_id = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="badly formed quiz id")
    quiz = await Quiz.objects.get_or_none(id=quiz_id, user_id=user.id)

    if quiz is None:
        return JSONResponse(status_code=404, content={"detail": "quiz not found"})
    pics_to_delete = []
    pic_name_regex = re.compile("^.*/(.{36}--.{36})$")
    for question in quiz.questions:
        try:
            if question["image"] is not None and not str(question["image"]).startswith("https://i.imgur.com/"):
                old_image_to_delete = pic_name_regex.match(question["image"])
                if old_image_to_delete is not None:
                    pics_to_delete.append(old_image_to_delete.group(1))
        except KeyError:
            pass
    if len(pics_to_delete) != 0:
        await storage.delete(pics_to_delete)
    meilisearch.index(settings.meilisearch_index).delete_document(str(quiz.id))
    return await quiz.delete()


@router.get("/export_data/{export_token}", response_class=StreamingResponse)
async def export_quiz_answers(export_token: str, game_pin: str):
    data = await redis.get(f"export_token:{export_token}")
    if data is None:
        raise HTTPException(status_code=404, detail="export token not found")
    data = json.loads(data)
    data2 = await redis.get(f"game:{game_pin}")
    game_data = PlayGame.model_validate_json(data2)
    quiz = await Quiz.objects.get_or_none(id=game_data.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="quiz not found")

    player_fields = await redis.hgetall(f"game:{game_pin}:players:custom_fields")
    score_data = await redis.hgetall(f"game_session:{game_pin}:player_scores")
    spreadsheet = await generate_spreadsheet(
        quiz=quiz, quiz_results=data, player_fields=player_fields, player_scores=score_data
    )

    def iter_file():
        yield from spreadsheet

    await redis.delete(f"export_token:{export_token}")
    return StreamingResponse(
        iter_file(),
        media_type="application/vnd.ms-excel",
        headers={
            "Content-Disposition": f"attachment;filename=ClassQuiz-{urllib.parse.quote(quiz.title)}-{datetime.now().strftime('%m-%d-%Y')}.xlsx"  # noqa: E501
        },
    )


@router.post("/excel-import")
async def import_from_excel(file: UploadFile = File(), user: User = Depends(get_current_user)) -> Quiz:
    quiz = await handle_import_from_excel(file.file, user)
    return Quiz.model_validate(quiz.model_dump(exclude={"user_id": ...}))
