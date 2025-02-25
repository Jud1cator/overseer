import re
import sqlite3

import dotenv
from fastapi import Depends, FastAPI

from app.service.config import AppConfig, get_config
from app.service.models import PachcaMessage, TicketStatusChange
from app.service.pachca_client import PachcaClient

dotenv.load_dotenv()

app = FastAPI()

conn = sqlite3.connect("bot.db")
db = conn.cursor()
db.execute(
    """
    CREATE TABLE IF NOT EXISTS tickets (
        issue_key TEXT,
        chat_id INT,
        message_id INT,
        PRIMARY KEY (issue_key, chat_id)
    )
    """
)


@app.post("/subscribe")
def subscribe(message: PachcaMessage, config: AppConfig = Depends(get_config)):
    issue_key = re.findall(f"{config.tracker_queue_key}-\\d+", message.content)
    if len(issue_key) == 0:
        raise ValueError("No issue key found")
    issue_key = issue_key[0]
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tickets VALUES (?, ?, ?)
        ON CONFLICT (issue_key, chat_id) DO UPDATE SET
            message_id=excluded.message_id;
        """,
        (
            issue_key,
            message.chat_id,
            message.id,
        ),
    )
    conn.commit()
    pachca_client = PachcaClient(token=config.pachca_token)
    pachca_client.send_message(
        chat_id=message.chat_id,
        text=f"Я сообщу вам об изменении статуса тикета {issue_key}",
        parent_message_id=message.id,
    )


@app.post("/unsubscribe")
def unsubscribe(message: PachcaMessage, config: AppConfig = Depends(get_config)):
    issue_key = re.findall(f"{config.tracker_queue_key}-\\d+", message.content)
    if len(issue_key) == 0:
        raise ValueError("No issue key found")
    issue_key = issue_key[0]
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM tickets
        WHERE issue_key = ? AND chat_id = ?
        """,
        (
            issue_key,
            message.chat_id,
        ),
    )
    conn.commit()
    pachca_client = PachcaClient(token=config.pachca_token)
    pachca_client.send_message(
        chat_id=message.chat_id,
        text=f"Тикет {issue_key} больше не отслеживается в этом треде",
        parent_message_id=message.id,
    )


@app.post("/ticket_status_change")
def ticket_status_change(ticket: TicketStatusChange, config: AppConfig = Depends(get_config)):
    if len(config.tracker_status_list) > 0 and ticket.status not in config.tracker_status_list:
        return f"Status {ticket.issue_key} is not tracked"
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    issue_info = cur.execute(
        "SELECT chat_id, message_id FROM tickets WHERE issue_key = ?",
        (ticket.issue_key,),
    ).fetchall()
    if len(issue_info) == 0:
        return f"Issue {ticket.issue_key} is not tracked"
    pachca_client = PachcaClient(token=config.pachca_token)
    # TODO rewrite to async
    for chat_id, message_id in issue_info:
        pachca_client.send_message(
            chat_id=chat_id,
            text=f"Тикет {ticket.issue_key} был переведён в статус {ticket.status}",
            parent_message_id=message_id,
        )
