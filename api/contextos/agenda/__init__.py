"""Contexto delimitado `agenda`: motor de agendamiento, solapamiento y concurrencia.

Sobre `supabase/migrations/006_reservas.sql` (`reservas`, `reserva_servicios`).

Pendiente (PR futuro) -- esqueleto de carpetas dejado solo para fijar la convención de
capas (`dominio/aplicacion/infraestructura/interfaces`), sin código todavía. Si necesita
algo de `identidad` (p.ej. validar que un usuario es barbero activo del tenant), debe
importar de `contextos.identidad.aplicacion.contexto_publico`, nunca de su
`dominio`/`infraestructura` internos.
"""
