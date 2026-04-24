"""Tool registry.

Adding a new tool module:
    1. Create ``kestrel_mcp/tools/<name>_tool.py`` subclassing ``ToolModule``.
    2. Import it below and append an instance to :func:`load_modules`.
    3. Add a matching ``tools.<name>`` block to ``config/default.yaml``.
"""

from __future__ import annotations

from ..config import Settings
from ..plugins import load_plugin_modules
from ..security import ScopeGuard
from .base import ToolModule


def load_modules(settings: Settings, scope_guard: ScopeGuard) -> list[ToolModule]:
    """Instantiate every bundled tool module in a deterministic order.

    Only modules marked ``enabled=True`` in the effective configuration are
    returned. This makes it cheap to ship a conservative default config
    where dangerous modules are opt-in.
    """

    from .amass_tool import AmassModule
    from .bloodhound_tool import BloodHoundModule
    from .caido_tool import CaidoModule
    from .engagement_tool import EngagementModule
    from .evilginx_tool import EvilginxModule
    from .ffuf_tool import FfufModule
    from .hashcat_tool import HashcatModule
    from .havoc_tool import HavocModule
    from .httpx_tool import HttpxModule
    from .impacket_tool import ImpacketModule
    from .katana_tool import KatanaModule
    from .ligolo_tool import LigoloModule
    from .netexec_tool import NetExecModule
    from .nmap_tool import NmapModule
    from .nuclei_tool import NucleiModule
    from .readiness_tool import ReadinessModule
    from .shodan_tool import ShodanModule
    from .sliver_tool import SliverModule
    from .sqlmap_tool import SqlmapModule
    from .subfinder_tool import SubfinderModule

    candidates: list[ToolModule] = [
        # Management / admin first — these don't depend on external binaries
        # and should always appear in the schema.
        EngagementModule(settings, scope_guard),
        ReadinessModule(settings, scope_guard),
        # External-tool-backed modules follow.
        ShodanModule(settings, scope_guard),
        NucleiModule(settings, scope_guard),
        SubfinderModule(settings, scope_guard),
        AmassModule(settings, scope_guard),
        HttpxModule(settings, scope_guard),
        KatanaModule(settings, scope_guard),
        NmapModule(settings, scope_guard),
        FfufModule(settings, scope_guard),
        SqlmapModule(settings, scope_guard),
        ImpacketModule(settings, scope_guard),
        NetExecModule(settings, scope_guard),
        HashcatModule(settings, scope_guard),
        BloodHoundModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
        LigoloModule(settings, scope_guard),
        SliverModule(settings, scope_guard),
        HavocModule(settings, scope_guard),
        EvilginxModule(settings, scope_guard),
    ]
    bundled = [m for m in candidates if m.enabled()]
    plugins = load_plugin_modules(settings, scope_guard)
    return bundled + plugins


__all__ = ["ToolModule", "load_modules"]
