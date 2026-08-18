/**
 * Encabezado de sección con el badge "en directo" -- punto rojo pulsante (`senal`) + texto,
 * el mismo lenguaje visual en todas las piezas que muestran datos en tiempo real (mapa de
 * negocios, tablero de fila). Un único lugar para no repetir el mismo bloque JSX carácter
 * por carácter en cada consumidor.
 */
export function EncabezadoEnVivo({ titulo }: { titulo: string }) {
  return (
    <div className="flex items-center justify-between">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-hueso-atenuado">
        {titulo}
      </p>
      <span className="flex items-center gap-1.5 font-mono text-[11px] text-senal-texto">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-senal opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-senal" />
        </span>
        en directo
      </span>
    </div>
  );
}
