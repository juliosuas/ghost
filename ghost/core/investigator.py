"""Main GhostInvestigator — orchestrates all OSINT modules and AI analysis."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from ghost.core.config import config
from ghost.core.correlator import Correlator
from ghost.core.report_generator import ReportGenerator
from ghost.modules.username import UsernameModule
from ghost.modules.email import EmailModule
from ghost.modules.phone import PhoneModule
from ghost.modules.social import SocialModule
from ghost.modules.domain import DomainModule
from ghost.modules.image import ImageModule
from ghost.modules.darkweb import DarkWebModule
from ghost.modules.geolocation import GeolocationModule
from ghost.ai.analyzer import AIAnalyzer
from ghost.ai.summarizer import Summarizer


INPUT_TYPE_MODULES = {
    "username": ["username", "social", "darkweb"],
    "email": ["email", "username", "social", "darkweb"],
    "phone": ["phone", "social"],
    "domain": ["domain", "geolocation"],
    "image": ["image"],
    "name": ["username", "social", "darkweb"],
    "auto": [],
}


def _detect_input_type(target: str) -> str:
    if "@" in target and "." in target:
        return "email"
    if target.startswith("+") or target.replace("-", "").replace(" ", "").isdigit():
        return "phone"
    if "." in target and " " not in target and len(target.split(".")[-1]) <= 6:
        return "domain"
    if " " in target:
        return "name"
    return "username"


class Investigation:
    """Represents a single investigation with all collected data."""

    def __init__(self, target: str, input_type: str, scope: str = "", authorized_use: bool = False):
        self.id = str(uuid.uuid4())
        self.target = target
        self.input_type = input_type
        self.scope = scope
        self.authorized_use = authorized_use
        self.started_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None
        self.status = "pending"
        self.findings: dict = {}
        self.correlations: dict = {}
        self.ai_analysis: dict = {}
        self.summary: str = ""
        self.risk_score: float = 0.0
        self.errors: list = []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target": self.target,
            "input_type": self.input_type,
            "scope": self.scope,
            "authorized_use": self.authorized_use,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "findings": self.findings,
            "correlations": self.correlations,
            "ai_analysis": self.ai_analysis,
            "summary": self.summary,
            "risk_score": self.risk_score,
            "errors": self.errors,
        }


class GhostInvestigator:
    """Main investigation orchestrator."""

    def __init__(self, config_override=None):
        self.config = config_override or config
        self._modules = {
            "username": UsernameModule(self.config),
            "email": EmailModule(self.config),
            "phone": PhoneModule(self.config),
            "social": SocialModule(self.config),
            "domain": DomainModule(self.config),
            "image": ImageModule(self.config),
            "darkweb": DarkWebModule(self.config),
            "geolocation": GeolocationModule(self.config),
        }
        self.correlator = Correlator(self.config)
        self.analyzer = AIAnalyzer(self.config)
        self.summarizer = Summarizer(self.config)
        self.report_generator = ReportGenerator()
        self._progress_callback = None

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def _report_progress(self, module: str, status: str, detail: str = ""):
        if self._progress_callback:
            self._progress_callback(module, status, detail)

    def investigate(
        self,
        target: str,
        input_type: str = "auto",
        modules: Optional[list] = None,
        scope: str = "",
        authorized_use: bool = False,
    ) -> Investigation:
        """Run a full investigation synchronously."""
        return asyncio.run(self.investigate_async(target, input_type, modules, scope, authorized_use))

    async def investigate_async(
        self,
        target: str,
        input_type: str = "auto",
        modules: Optional[list] = None,
        scope: str = "",
        authorized_use: bool = False,
    ) -> Investigation:
        """Run a full investigation asynchronously."""
        if input_type == "auto":
            input_type = _detect_input_type(target)

        investigation = Investigation(target, input_type, scope=scope, authorized_use=authorized_use)
        investigation.status = "running"

        # Determine which modules to run
        module_names = modules or INPUT_TYPE_MODULES.get(input_type, [])
        module_names = [m for m in module_names if m in self.config.enabled_modules]

        # Phase 1: Collect data from all modules concurrently
        self._report_progress("collector", "start", f"Running {len(module_names)} modules")
        tasks = []
        for name in module_names:
            if name in self._modules:
                tasks.append(self._run_module(name, target, input_type, investigation))

        await asyncio.gather(*tasks)

        # Phase 2: Correlate findings
        self._report_progress("correlator", "start", "Correlating findings")
        try:
            investigation.correlations = await self.correlator.correlate(
                investigation.findings
            )
        except Exception as e:
            investigation.errors.append(f"Correlation error: {e}")

        # Phase 3: AI Analysis
        self._report_progress("ai", "start", "Running AI analysis")
        try:
            investigation.ai_analysis = await self.analyzer.analyze(
                target, input_type, investigation.findings, investigation.correlations
            )
            investigation.risk_score = investigation.ai_analysis.get("risk_score", 0.0)
        except Exception as e:
            investigation.errors.append(f"AI analysis error: {e}")

        # Phase 4: Generate summary
        self._report_progress("summarizer", "start", "Generating summary")
        try:
            investigation.summary = await self.summarizer.summarize(investigation)
        except Exception as e:
            investigation.errors.append(f"Summary error: {e}")

        investigation.status = "completed"
        investigation.completed_at = datetime.now(timezone.utc)
        self._report_progress("complete", "done", "Investigation complete")

        return investigation

    async def _run_module(
        self, name: str, target: str, input_type: str, investigation: Investigation
    ):
        """Run a single OSINT module with error handling."""
        self._report_progress(name, "running", f"Scanning {name}")
        try:
            module = self._modules[name]
            result = await module.run(target, input_type)
            investigation.findings[name] = result
            self._report_progress(name, "done", f"{name} complete")
        except Exception as e:
            investigation.errors.append(f"{name}: {e}")
            investigation.findings[name] = {"error": str(e)}
            self._report_progress(name, "error", str(e))

    def generate_report(
        self, investigation: Investigation, format: str = "html", output_path: str = None
    ) -> str:
        """Generate a report from an investigation."""
        return self.report_generator.generate(investigation, format, output_path)
