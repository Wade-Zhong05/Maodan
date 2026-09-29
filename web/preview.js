/* Plays Maodan's sprite atlas on a canvas, for the animation page (web/index.html).
 *
 * The page is usually opened straight from disk, where browsers refuse fetch(). So the frame layout
 * arrives as ../assets/animation.js (window.MAODAN_ANIMATION) and the sheet as a plain image.
 */
(() => {
  const ASSET_BASE = '../assets/'
  let assetsPromise = null

  function loadImage(path) {
    return new Promise((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error(`Maodan's artwork failed to load: ${ASSET_BASE}${path}`))
      image.src = ASSET_BASE + path
    })
  }

  function loadAssets() {
    if (!assetsPromise) {
      const manifest = window.MAODAN_ANIMATION
      const loading = manifest
        ? loadImage(manifest.spritesheet).then((sprite) => ({ manifest, sprite }))
        : Promise.reject(new Error("Maodan's animation data is missing: assets/animation.js"))
      assetsPromise = loading.catch((error) => {
        assetsPromise = null
        throw error
      })
    }
    return assetsPromise
  }

  function mount(canvas, { action = 'idle', onError } = {}) {
    const context = canvas.getContext('2d')
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const cleanupCallbacks = []
    let assets
    let disposed = false
    let visible = true
    let requestId = 0
    let startedAt = performance.now()
    let currentAction = action
    let lastDrawnFrame = ''

    function listen(target, event, listener) {
      target.addEventListener(event, listener)
      cleanupCallbacks.push(() => target.removeEventListener(event, listener))
    }

    function drawFrame(actionName, frame) {
      const { manifest, sprite } = assets
      const animation = manifest.animations[actionName]
      const key = `${actionName}:${frame}`
      if (key === lastDrawnFrame) return
      lastDrawnFrame = key
      const { frameWidth, frameHeight, columns } = manifest
      const cell = animation.row * columns + frame
      context.clearRect(0, 0, frameWidth, frameHeight)
      context.drawImage(sprite,
        (cell % columns) * frameWidth, Math.floor(cell / columns) * frameHeight,
        frameWidth, frameHeight, 0, 0, frameWidth, frameHeight)
      canvas.dataset.ready = 'true'
      canvas.dataset.action = actionName
      canvas.dataset.frame = String(frame)
    }

    function tick(now) {
      requestId = 0
      if (disposed || !assets || !context) return
      if (reducedMotion.matches) {
        drawFrame('idle', 0)
        return
      }
      if (document.hidden || !visible) return
      let animation = assets.manifest.animations[currentAction]
      if (!animation) {
        currentAction = 'idle'
        animation = assets.manifest.animations.idle
      }
      // "look" has no per-frame timings: it steps through its sixteen directions at a steady fps.
      const duration = animation.durations
        ? animation.durations.reduce((sum, value) => sum + value, 0)
        : animation.frames * 1000 / animation.fps
      let frame = 0
      let offset = (now - startedAt) % duration
      if (animation.durations) {
        while (frame < animation.frames - 1 && offset >= animation.durations[frame]) {
          offset -= animation.durations[frame++]
        }
      } else {
        frame = Math.floor(offset * animation.fps / 1000) % animation.frames
      }
      drawFrame(currentAction, frame)
      requestId = requestAnimationFrame(tick)
    }

    function restart() {
      cancelAnimationFrame(requestId)
      requestId = 0
      startedAt = performance.now()
      tick(startedAt)
    }

    function resizeCanvas() {
      const { frameWidth, frameHeight } = assets.manifest
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      const width = Math.round((canvas.clientWidth || frameWidth) * pixelRatio)
      const height = Math.round((canvas.clientHeight || frameHeight) * pixelRatio)
      if (canvas.width === width && canvas.height === height) return false
      canvas.width = width
      canvas.height = height
      context.setTransform(width / frameWidth, 0, 0, height / frameHeight, 0, 0)
      context.imageSmoothingEnabled = true
      lastDrawnFrame = ''
      return true
    }

    function play(name) {
      if (disposed || reducedMotion.matches) return
      if (assets && !assets.manifest.animations[name]) return
      currentAction = name
      restart()
    }

    listen(reducedMotion, 'change', restart)
    listen(document, 'visibilitychange', restart)
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting
        restart()
      })
      observer.observe(canvas)
      cleanupCallbacks.push(() => observer.disconnect())
    }

    loadAssets().then((loaded) => {
      if (disposed || !context) return
      assets = loaded
      resizeCanvas()
      if ('ResizeObserver' in window) {
        const observer = new ResizeObserver(() => {
          if (resizeCanvas()) restart()
        })
        observer.observe(canvas)
        cleanupCallbacks.push(() => observer.disconnect())
      }
      restart()
    }).catch((error) => {
      if (disposed) return
      console.warn(error.message)
      onError?.(error)
    })

    return {
      play,
      destroy() {
        disposed = true
        cancelAnimationFrame(requestId)
        cleanupCallbacks.forEach((cleanup) => cleanup())
      },
    }
  }

  window.MaodanPreview = { mount }
})()
