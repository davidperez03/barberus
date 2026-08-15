"""Contexto delimitado `identidad`: perfiles, roles y sesiones.

Sobre `supabase/migrations/009_identidad_autenticacion.sql` y
`010_identidad_extendida.sql`. Todo otro contexto que necesite algo de acá debe importar
de `contextos.identidad.aplicacion.contexto_publico`, nunca de `dominio`/`infraestructura`
directamente.
"""
