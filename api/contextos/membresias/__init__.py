"""Contexto delimitado `membresias`: niveles y tracking de visitas (sin cobro).

Sobre `supabase/migrations/008_membresias.sql` (`niveles_membresia`,
`membresias_cliente`, `historial_nivel_membresia_cliente`).

Pendiente (PR futuro) -- esqueleto de carpetas dejado solo para fijar la convención de
capas (`dominio/aplicacion/infraestructura/interfaces`), sin código todavía. Si necesita
algo de `identidad`, debe importar de `contextos.identidad.aplicacion.contexto_publico`,
nunca de su `dominio`/`infraestructura` internos.
"""
