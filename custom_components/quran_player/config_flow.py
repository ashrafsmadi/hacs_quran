"""UI configuration flow for Quran Player."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .catalog import RECITERS
from .const import (
    CONF_DEFAULT_RECITER,
    CONF_DEFAULT_VOLUME,
    CONF_MEDIA_PLAYERS,
    DEFAULT_RECITER,
    DEFAULT_VOLUME,
    DOMAIN,
    NAME,
)


def _reciter_options() -> list[selector.SelectOptionDict]:
    """Return labeled stable values for the config flow."""
    return [
        selector.SelectOptionDict(value=reciter.key, label=reciter.display_name)
        for reciter in RECITERS
    ]


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the config/options schema with current suggested values."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_MEDIA_PLAYERS,
                default=defaults.get(CONF_MEDIA_PLAYERS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    filter=selector.EntityFilterSelectorConfig(domain="media_player"),
                    multiple=True,
                    reorder=True,
                )
            ),
            vol.Required(
                CONF_DEFAULT_RECITER,
                default=defaults.get(CONF_DEFAULT_RECITER, DEFAULT_RECITER),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_reciter_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_DEFAULT_VOLUME,
                default=defaults.get(CONF_DEFAULT_VOLUME, DEFAULT_VOLUME * 100),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _validated_options(
    hass: Any, user_input: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize targets and reject empty, recursive, or wrong-domain values."""
    raw_targets = user_input.get(CONF_MEDIA_PLAYERS, [])
    if isinstance(raw_targets, str):
        raw_targets = [raw_targets]
    targets = list(dict.fromkeys(raw_targets))
    if not targets:
        return None, "no_targets"
    if any(
        not isinstance(target, str) or not target.startswith("media_player.")
        for target in targets
    ):
        return None, "invalid_target"

    registry = er.async_get(hass)
    if any(
        (entry := registry.async_get(target)) is not None and entry.platform == DOMAIN
        for target in targets
    ):
        return None, "recursive_target"

    return {
        CONF_MEDIA_PLAYERS: targets,
        CONF_DEFAULT_RECITER: user_input[CONF_DEFAULT_RECITER],
        CONF_DEFAULT_VOLUME: round(float(user_input[CONF_DEFAULT_VOLUME])),
    }, None


class QuranPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the singleton Quran Player setup flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one or more existing media-player outputs."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}
        if user_input is not None:
            options, error = _validated_options(self.hass, user_input)
            if error is None and options is not None:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data={}, options=options)
            errors["base"] = error or "invalid_target"

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> QuranPlayerOptionsFlow:
        """Return an automatically reloading options flow."""
        return QuranPlayerOptionsFlow()


class QuranPlayerOptionsFlow(OptionsFlowWithReload):
    """Edit outputs and defaults, then reload exactly once."""

    @override
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage mutable integration options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options, error = _validated_options(self.hass, user_input)
            if error is None and options is not None:
                return self.async_create_entry(title="", data=options)
            errors["base"] = error or "invalid_target"

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )
