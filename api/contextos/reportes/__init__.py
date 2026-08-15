"""Contexto delimitado `reportes`: agregados de solo lectura sobre el resto del dominio
(no-shows, ocupación, tiempos de fila) para el `dueno_sede`/`administrador_plataforma`.

No tiene migración propia -- lee (nunca escribe) datos de `agenda`/`fila`/`membresias` a
través de sus puertos/casos de uso públicos, igual que cualquier otro contexto.

Pendiente (PR futuro) -- esqueleto de carpetas dejado solo para fijar la convención de
capas (`dominio/aplicacion/infraestructura/interfaces`), sin código todavía.
"""
