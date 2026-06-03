"""Backend unit tests — FastAPI + SQLite in-memory"""
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure project root is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Set test flag BEFORE importing backend modules — prevents init_db from firing
os.environ["RISK_AGENT_TESTING"] = "true"

from sqlalchemy.pool import StaticPool
from backend.app.database import Base, get_db
from backend.app.main import create_app
from backend.models.task import Task, TaskLog
from backend.models.feature import FeatureVersion, FeatureMetric
from backend.models.user import User
from backend.services.task_service import create_task, get_task, get_task_list, add_task_log, update_task_status
from backend.auth.jwt import hash_password

# ---- Shared in-memory SQLite for tests ----
# Use StaticPool so all connections share the same in-memory database
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)

# Register models and create tables on in-memory engine
import backend.models  # noqa

# ---- Override DB dependency for all API tests ----
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_db():
    """Re-create all tables before each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create a TestClient with the in-memory DB. Override lifespan to no-op."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    # Replace lifespan with a no-op to avoid init_db on the file-level engine
    app.router.lifespan_context = None
    return TestClient(app)


@pytest.fixture
def test_user(client):
    """Register a test user and return auth token + username."""
    resp = client.post("/api/auth/register", json={"username": "testuser", "password": "testpass123"})
    assert resp.status_code == 201
    login_resp = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass123"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    return {"token": data["access_token"], "username": data["username"]}


def auth_header(token: str) -> dict:
    """Build Authorization header dict for authenticated requests."""
    return {"Authorization": f"Bearer {token}"}


# ==================== Health ====================

class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_version(self, client):
        resp = client.get("/api/health")
        assert resp.json()["version"] == "1.0.0"


# ==================== Tasks ====================

class TestTaskService:
    def test_create_task(self):
        db = TestingSessionLocal()
        task = create_task(db, name="测试任务", mode="mass_production")
        assert task.id is not None
        assert task.status == "pending"
        assert task.mode == "mass_production"
        db.close()

    def test_get_task(self):
        db = TestingSessionLocal()
        created = create_task(db, name="测试", mode="llm")
        fetched = get_task(db, created.id)
        assert fetched is not None
        assert fetched.name == "测试"
        db.close()

    def test_get_task_not_found(self):
        db = TestingSessionLocal()
        assert get_task(db, 999) is None
        db.close()

    def test_get_task_list(self):
        db = TestingSessionLocal()
        for i in range(5):
            create_task(db, name=f"任务{i}", mode="mass_production")
        items, total = get_task_list(db)
        assert total == 5
        assert len(items) == 5
        db.close()

    def test_get_task_list_pagination(self):
        db = TestingSessionLocal()
        for i in range(10):
            create_task(db, name=f"任务{i}", mode="mass_production")
        items, total = get_task_list(db, skip=5, limit=3)
        assert total == 10
        assert len(items) == 3
        db.close()

    def test_add_task_log(self):
        db = TestingSessionLocal()
        task = create_task(db, name="测试", mode="mass_production")
        add_task_log(db, task.id, "info", "测试日志")
        logs = db.query(TaskLog).filter(TaskLog.task_id == task.id).all()
        assert len(logs) == 1
        assert logs[0].message == "测试日志"
        db.close()

    def test_update_task_status(self):
        db = TestingSessionLocal()
        task = create_task(db, name="测试", mode="mass_production")
        update_task_status(db, task.id, status="running", progress=50.0)
        db.refresh(task)
        assert task.status == "running"
        assert task.progress == 50.0
        db.close()


class TestTaskAPI:
    def test_create_task_api(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.post("/api/tasks", data={"name": "API测试"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API测试"
        assert data["status"] in ("pending", "running", "completed")

    def test_create_task_auto_template(self, client, clean_db, test_user):
        """创建普通任务时会自动创建模板任务"""
        h = auth_header(test_user["token"])
        resp = client.post("/api/tasks", data={"name": "auto_tmpl"}, headers=h)
        assert resp.status_code == 200
        # 应该有两个任务：普通 + 模板
        list_resp = client.get("/api/tasks", headers=h)
        data = list_resp.json()
        assert data["total"] >= 2
        modes = {item["mode"] for item in data["items"]}
        assert "normal" in modes
        assert "template_task" in modes

    def test_list_tasks_empty(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/tasks", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_tasks_with_data(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        client.post("/api/tasks", data={"name": "T1"}, headers=h)
        client.post("/api/tasks", data={"name": "T2"}, headers=h)
        resp = client.get("/api/tasks", headers=h)
        data = resp.json()
        # 每个普通任务会同时创建一个模板任务，共4条
        assert data["total"] == 4
        assert len(data["items"]) == 4

    def test_get_task_detail(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        create = client.post("/api/tasks", data={"name": "detail"}, headers=h).json()
        resp = client.get(f"/api/tasks/{create['id']}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["name"] == "detail"

    def test_get_task_not_found(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/tasks/9999", headers=h)
        assert resp.status_code == 404

    def test_task_result_exists(self, client, clean_db, test_user):
        """GET /api/tasks/{id}/result returns passed_features.json contents"""
        h = auth_header(test_user["token"])
        create = client.post("/api/tasks", data={"name": "result"}, headers=h).json()
        resp = client.get(f"/api/tasks/{create['id']}/result", headers=h)
        # Returns 200 because passed_features.json exists on disk from pipeline runs
        assert resp.status_code == 200


# ==================== Agent / Orchestrator ====================

class TestAgentAPI:
    def test_orchestrator_status(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/agents/orchestrator/status", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "accumulated_passed" in data

    def test_orchestrator_logs_empty(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/agents/orchestrator/logs?lines=10", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "lines" in data

    def test_channel2_pending_empty(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/agents/reviews/channel2-pending", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 0

    def test_feature_review_empty(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/agents/reviews/feature-review", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "exists" in data


# ==================== Features ====================

class TestFeatureAPI:
    def _seed_metrics(self):
        db = TestingSessionLocal()
        for i in range(3):
            fm = FeatureMetric(
                version="v1",
                task_id=1,
                feature_name=f"feature_{i}",
                iv=0.1 * (i + 1),
                psi=0.05 * (i + 1),
                coverage=0.5 + 0.1 * i,
                is_passed=True if i < 2 else False,
            )
            db.add(fm)
        db.commit()
        fv = FeatureVersion(version="v1", task_id=1, total_features=3, passed_features=2)
        db.add(fv)
        db.commit()
        db.close()

    def test_feature_versions_empty(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/features/versions", headers=h)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_feature_versions_with_data(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        self._seed_metrics()
        resp = client.get("/api/features/versions", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_feature_version_detail(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        self._seed_metrics()
        resp = client.get("/api/features/versions/v1", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1"
        assert data["total"] == 3
        assert data["passed"] == 2

    def test_feature_version_not_found(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/features/versions/nonexistent", headers=h)
        assert resp.status_code == 404

    def test_feature_top(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        self._seed_metrics()
        resp = client.get("/api/features/top", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3

    def test_feature_top_limit(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        self._seed_metrics()
        resp = client.get("/api/features/top?n=2", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    def test_feature_stats(self, client, clean_db, test_user):
        h = auth_header(test_user["token"])
        resp = client.get("/api/features/stats", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "current_total" in data
        assert "accumulated_passed" in data
        assert "latest_version" in data
