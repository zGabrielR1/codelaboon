// Pointer-reactive dot field, adapted for the standalone web shell from the React Bits Dot Grid interaction.
(() => {
  const canvas = document.querySelector('#dot-field');
  const context = canvas?.getContext('2d');
  if (!context) return;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let pointer = null;
  let frame = 0;
  function draw() {
    frame = 0;
    const {width, height} = canvas.getBoundingClientRect();
    if (!width || !height) return;
    const scale = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    context.scale(scale, scale);
    context.fillStyle = getComputedStyle(canvas).getPropertyValue('--accent').trim();
    for (let y = 8; y < height; y += 14) {
      for (let x = 8; x < width; x += 14) {
        const dx = pointer ? x - pointer.x : 0;
        const dy = pointer ? y - pointer.y : 0;
        const influence = pointer ? Math.max(0, 1 - Math.hypot(dx, dy) / 90) : 0;
        const fade = (x / width) * (1 - y / height);
        context.globalAlpha = fade * .5 + influence * .35;
        context.beginPath();
        context.arc(x + dx * influence * .4, y + dy * influence * .4, 1 + influence, 0, Math.PI * 2);
        context.fill();
      }
    }
  }
  function schedule() {
    if (!frame) frame = requestAnimationFrame(draw);
  }
  canvas.parentElement.addEventListener('pointermove', event => {
    if (motion.matches || event.pointerType === 'touch') return;
    const box = canvas.getBoundingClientRect();
    pointer = {x: event.clientX - box.left, y: event.clientY - box.top};
    schedule();
  });
  canvas.parentElement.addEventListener('pointerleave', () => { pointer = null; schedule(); });
  new ResizeObserver(schedule).observe(canvas);
  new MutationObserver(schedule).observe(document.body, {attributes: true, attributeFilter: ['class']});
  motion.addEventListener('change', () => { pointer = null; schedule(); });
})();
