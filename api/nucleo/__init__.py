"""Shared kernel de Barberus.

Solo lo genuinamente transversal a TODOS los contextos delimitados: excepciones base,
tipos compartidos y configuración de conexión a Supabase. Deliberadamente pequeño -- si
algo es lógica de negocio de un contexto concreto (identidad, agenda, fila...), vive en
ese contexto, no acá.
"""
