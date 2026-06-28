"""Resolução de ``sku_canal`` -> ``sku_base`` via tabela ``sku_map``.

Regra 4 do CLAUDE.md: se não houver mapeamento, registrar pendência e NÃO
bloquear a importação.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sku_map import SkuMap, SkuPendencia


class SkuResolver:
    """Resolve SKUs de canal carregando o de-para em memória uma única vez."""

    def __init__(self, db: Session):
        self.db = db
        self._cache: dict[tuple[str, str], str] = {}
        for sm in db.execute(select(SkuMap)).scalars():
            self._cache[(sm.sku_canal, sm.canal)] = sm.sku_base
        # Pendências acumuladas nesta sessão (sku_canal, canal) -> SkuPendencia
        self._pendencias: dict[tuple[str, str], SkuPendencia] = {}

    def resolver(
        self,
        sku_canal: str,
        canal: str,
        *,
        id_anuncio: str | None = None,
        titulo: str | None = None,
    ) -> str | None:
        """Retorna ``sku_base`` ou ``None`` (registrando pendência neste caso)."""
        sku_canal = (sku_canal or "").strip()
        if not sku_canal:
            return None

        key = (sku_canal, canal)
        if key in self._cache:
            return self._cache[key]

        self._registrar_pendencia(sku_canal, canal, id_anuncio, titulo)
        return None

    def _registrar_pendencia(
        self, sku_canal: str, canal: str, id_anuncio: str | None, titulo: str | None
    ) -> None:
        key = (sku_canal, canal)
        if key in self._pendencias:
            self._pendencias[key].ocorrencias += 1
            return

        existente = self.db.execute(
            select(SkuPendencia).where(
                SkuPendencia.sku_canal == sku_canal,
                SkuPendencia.canal == canal,
            )
        ).scalar_one_or_none()

        if existente is not None:
            existente.ocorrencias += 1
            self._pendencias[key] = existente
        else:
            nova = SkuPendencia(
                sku_canal=sku_canal,
                canal=canal,
                id_anuncio=id_anuncio,
                titulo=titulo,
                ocorrencias=1,
            )
            self.db.add(nova)
            self._pendencias[key] = nova

    @property
    def pendencias(self) -> list[SkuPendencia]:
        return list(self._pendencias.values())
