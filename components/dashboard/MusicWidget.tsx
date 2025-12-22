export function MusicWidget() {
  return (
    <div className="h-full w-full overflow-hidden rounded-lg relative group">
      <div className="absolute inset-0 bg-linear-to-br from-purple-500/20 via-pink-500/20 to-orange-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none z-10" />

      {/* 
        Using a Lofi Girl stream embed or similar. 
        Note: Autoplay usually blocked by browsers unless muted, keeping it simple.
      */}
      <iframe
        width="100%"
        height="100%"
        src="https://www.youtube.com/embed/jfKfPfyJRdk?controls=0&modestbranding=1"
        title="YouTube video player"
        frameBorder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerPolicy="strict-origin-when-cross-origin"
        allowFullScreen
        className="opacity-90 group-hover:opacity-100 transition-opacity duration-300 scale-in"
      ></iframe>
    </div>
  );
}
