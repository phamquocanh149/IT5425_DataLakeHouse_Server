"""System module wiring: readiness provider + router."""

from fastapi import APIRouter

from climate_platform.modules.system.controller import system_router


def build_system_module() -> APIRouter:
    return system_router()
