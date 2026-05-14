import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "Library" / "Application Support" / "AudioQAS" / "history.db"


class HistoryManager:
    def __init__(self):
        self._ensure_db()

    def _ensure_db(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                model TEXT NOT NULL,
                model_version TEXT NOT NULL,
                files_count INT NOT NULL,
                statistics TEXT NOT NULL,
                processing_time INT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_files (
                eval_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_sr INT NOT NULL,
                original_channels INT NOT NULL,
                duration REAL NOT NULL,
                preprocessed INT NOT NULL,
                ovrl_score REAL NOT NULL,
                ovrl_grade TEXT NOT NULL,
                ovrl_desc TEXT NOT NULL,
                sig_score REAL NOT NULL,
                sig_grade TEXT NOT NULL,
                sig_desc TEXT NOT NULL,
                bak_score REAL NOT NULL,
                bak_grade TEXT NOT NULL,
                bak_desc TEXT NOT NULL,
                FOREIGN KEY (eval_id) REFERENCES evaluations(id)
            )
        """)
        conn.commit()
        conn.close()

    def save_evaluation(self, results: list, processing_time_ms: int) -> str:
        eval_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().isoformat()
        files_count = len(results)
        type_ = "批量" if files_count > 1 else "单文件"

        if results:
            model = results[0].get("model_name", "")
            model_version = results[0].get("model_version", "")
        else:
            model = ""
            model_version = ""

        ovrl_scores = [r["dimensions"]["OVRL"]["score"] for r in results]
        sig_scores = [r["dimensions"]["SIG"]["score"] for r in results]
        bak_scores = [r["dimensions"]["BAK"]["score"] for r in results]
        statistics = {
            "ovrl_mean": sum(ovrl_scores) / len(ovrl_scores) if ovrl_scores else 0,
            "ovrl_min": min(ovrl_scores) if ovrl_scores else 0,
            "ovrl_max": max(ovrl_scores) if ovrl_scores else 0,
            "sig_mean": sum(sig_scores) / len(sig_scores) if sig_scores else 0,
            "bak_mean": sum(bak_scores) / len(bak_scores) if bak_scores else 0,
        }

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO evaluations (id, timestamp, type, model, model_version, files_count, statistics, processing_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (eval_id, timestamp, type_, model, model_version, files_count, json.dumps(statistics), processing_time_ms),
        )
        for r in results:
            dims = r["dimensions"]
            filename = r.get("filename", os.path.basename(r["file_path"]))
            conn.execute(
                "INSERT INTO evaluation_files (eval_id, file_path, filename, original_sr, original_channels, duration, preprocessed, ovrl_score, ovrl_grade, ovrl_desc, sig_score, sig_grade, sig_desc, bak_score, bak_grade, bak_desc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    eval_id, r["file_path"], filename, r["original_sr"],
                    r["original_channels"], r["duration"], int(r["preprocessed"]),
                    dims["OVRL"]["score"], dims["OVRL"]["grade"], dims["OVRL"]["description"],
                    dims["SIG"]["score"], dims["SIG"]["grade"], dims["SIG"]["description"],
                    dims["BAK"]["score"], dims["BAK"]["grade"], dims["BAK"]["description"],
                ),
            )
        conn.commit()
        conn.close()
        return eval_id

    def get_all_evaluations(self) -> list:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM evaluations ORDER BY timestamp DESC").fetchall()
        conn.close()
        result = []
        for row in rows:
            d = dict(row)
            d["statistics"] = json.loads(d["statistics"])
            result.append(d)
        return result

    def get_evaluation_detail(self, eval_id: str) -> list:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM evaluation_files WHERE eval_id = ?", (eval_id,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_evaluation(self, eval_id: str):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM evaluation_files WHERE eval_id = ?", (eval_id,))
        conn.execute("DELETE FROM evaluations WHERE id = ?", (eval_id,))
        conn.commit()
        conn.close()

    def delete_all(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM evaluation_files")
        conn.execute("DELETE FROM evaluations")
        conn.commit()
        conn.close()