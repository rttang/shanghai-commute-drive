import * as THREE from 'three'
import Experience from '../Experience.js'

/**
 * GameManager - Complete game system with scoring, timer, laps, and states
 */
export default class GameManager {
    constructor() {
        this.experience = new Experience()
        this.scene = this.experience.scene
        this.time = this.experience.time
        
        // Game state
        this.state = 'ready' // ready, playing, paused, gameOver
        this.score = 0
        this.coins = 0
        this.coinsCollected = 0
        this.totalCoins = 0
        this.timeRemaining = 120 // seconds
        this.timeLimit = 120
        this.bestScore = this.loadBestScore()
        this.lastUpdate = 0
        
        // Lap tracking
        this.currentLap = 1
        this.maxLaps = 3
        // Start/finish is the checkered line placed in Floor.addStartingLine()
        // It spans roughly x ∈ [41..59] and sits around z ≈ 10..13.
        this.startFinish = {
            xMin: 40,
            xMax: 60,
            z: 11.5,
            zWindow: 2.0,
            cooldownMs: 2000
        }
        this.lastStartFinishSide = null
        this.lastLapCrossTime = 0
        this.lapCompleteBonus = 100
        
        // Combo system
        this.combo = 0
        this.comboTimer = 0
        this.comboTimeout = 2.0 // seconds to keep combo
        this.lastCoinTime = 0
        
        // Settings (can be updated from GameSettings)
        this.settings = {
            coinValue: 10,
            timeLimit: 120
        }
        
        // Collectibles
        this.collectibles = []
        this.collectibleGroup = new THREE.Group()
        this.scene.add(this.collectibleGroup)
        
        // Audio context for sounds (if supported)
        this.setupAudio()
        
        // Create UI
        this.createUI()
        
        // Spawn initial coins
        this.spawnCoins()
        
        // Bind keyboard events
        this.bindEvents()
    }
    
    setupAudio() {
        // Simple audio context for coin sounds
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
        } catch (e) {
            this.audioContext = null
        }
    }
    
    playSound(frequency = 800, duration = 0.1, type = 'square') {
        if (!this.audioContext) return
        
        try {
            const oscillator = this.audioContext.createOscillator()
            const gainNode = this.audioContext.createGain()
            
            oscillator.connect(gainNode)
            gainNode.connect(this.audioContext.destination)
            
            oscillator.frequency.value = frequency
            oscillator.type = type
            
            gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime)
            gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + duration)
            
            oscillator.start(this.audioContext.currentTime)
            oscillator.stop(this.audioContext.currentTime + duration)
        } catch (e) {
            // Audio failed silently
        }
    }
    
    bindEvents() {
        window.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && this.state === 'ready') {
                this.startGame()
            } else if (e.code === 'KeyR' && this.state === 'gameOver') {
                this.restartGame()
            } else if (e.code === 'Escape') {
                if (this.state === 'playing') {
                    this.pauseGame()
                } else if (this.state === 'paused') {
                    this.resumeGame()
                }
            }
        })
    }

    createUI() {
        // Remove old UI if exists
        const oldUI = document.getElementById('game-ui')
        if (oldUI) oldUI.remove()
        
        // Main game UI container
        this.uiContainer = document.createElement('div')
        this.uiContainer.id = 'game-ui'
        this.uiContainer.innerHTML = `
            <!-- Start Screen -->
            <div id="start-screen" class="game-screen">
                <div class="game-title">🏎️ COIN RACER</div>
                <div class="game-subtitle">Collect all coins before time runs out!</div>
                <div class="controls-info">
                    <div>⬆️⬇️ Accelerate/Brake • ⬅️➡️ Steer</div>
                    <div>SPACE Jump • B Boost • C Color</div>
                </div>
                <div class="start-prompt">Press SPACE to Start</div>
                <div class="best-score">🏆 Best: <span id="best-score-value">0</span></div>
            </div>
            
            <!-- In-Game HUD -->
            <div id="game-hud" class="game-hud hidden">
                <div class="hud-top">
                    <div class="hud-score">
                        <span class="coin-icon">🪙</span>
                        <span id="coin-count">0</span>/<span id="total-coins">0</span>
                    </div>
                    <div class="hud-center">
                        <div class="hud-lap">LAP <span id="lap-count">1</span>/3</div>
                    </div>
                    <div class="hud-timer">
                        <span class="timer-icon">⏱️</span>
                        <span id="time-remaining">2:00</span>
                    </div>
                </div>
                <div class="hud-left">
                    <div class="hud-points">Score: <span id="score-value">0</span></div>
                    <div class="hud-speed">🏎️ <span id="speed-value">0</span> km/h</div>
                </div>
                <div class="hud-combo hidden" id="combo-display">
                    <span id="combo-count">2</span>x COMBO!
                </div>
            </div>
            
            <!-- Pause Screen -->
            <div id="pause-screen" class="game-screen hidden">
                <div class="pause-title">⏸️ PAUSED</div>
                <div class="pause-prompt">Press ESC to Resume</div>
            </div>
            
            <!-- Game Over Screen -->
            <div id="gameover-screen" class="game-screen hidden">
                <div class="gameover-title" id="gameover-title">⏰ TIME'S UP!</div>
                <div class="final-stats">
                    <div>Coins: <span id="final-coins">0</span></div>
                    <div>Laps: <span id="final-laps">0</span></div>
                    <div>Score: <span id="final-score">0</span></div>
                    <div class="new-best hidden" id="new-best">🏆 NEW BEST!</div>
                </div>
                <div class="restart-prompt">Press R to Restart</div>
            </div>
        `
        document.body.appendChild(this.uiContainer)
        
        // Add styles
        this.addStyles()
        
        // Update best score display
        document.getElementById('best-score-value').textContent = this.bestScore
    }
    
    addStyles() {
        // Remove old styles if exist
        const oldStyle = document.getElementById('game-styles')
        if (oldStyle) oldStyle.remove()
        
        const style = document.createElement('style')
        style.id = 'game-styles'
        style.textContent = `
            #game-ui {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 100;
                font-family: 'Press Start 2P', 'Arial', sans-serif;
            }
            
            .game-screen {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                background: rgba(0, 0, 0, 0.7);
                color: white;
                text-align: center;
            }
            
            .hidden {
                display: none !important;
            }
            
            /* Start Screen */
            .game-title {
                font-size: 48px;
                color: #FFD700;
                text-shadow: 4px 4px 0 #FF3D00, 6px 6px 0 rgba(0,0,0,0.3);
                margin-bottom: 20px;
                animation: titleBounce 0.5s ease infinite alternate;
            }
            
            @keyframes titleBounce {
                from { transform: scale(1); }
                to { transform: scale(1.02); }
            }
            
            .game-subtitle {
                font-size: 14px;
                color: #fff;
                margin-bottom: 40px;
                opacity: 0.9;
            }
            
            .controls-info {
                font-size: 12px;
                color: #aaa;
                margin-bottom: 40px;
                line-height: 2;
            }
            
            .start-prompt {
                font-size: 18px;
                color: #4ADE80;
                animation: blink 1s ease infinite;
            }
            
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }
            
            .best-score {
                margin-top: 30px;
                font-size: 14px;
                color: #FFD700;
            }
            
            /* In-Game HUD */
            .game-hud {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                padding: 20px;
                box-sizing: border-box;
            }
            
            .hud-top {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .hud-score, .hud-timer {
                background: rgba(0, 0, 0, 0.6);
                padding: 12px 20px;
                border-radius: 25px;
                font-size: 16px;
                color: white;
                display: flex;
                align-items: center;
                gap: 8px;
                border: 2px solid rgba(255,255,255,0.3);
            }
            
            .hud-center {
                position: absolute;
                left: 50%;
                transform: translateX(-50%);
            }
            
            .hud-lap {
                background: linear-gradient(135deg, #FF3D00, #FF6600);
                padding: 12px 25px;
                border-radius: 25px;
                font-size: 18px;
                font-weight: bold;
                color: white;
                border: 3px solid #FFD700;
                text-shadow: 2px 2px 0 rgba(0,0,0,0.5);
            }
            
            .coin-icon, .timer-icon {
                font-size: 20px;
            }
            
            .hud-left {
                position: absolute;
                top: 80px;
                left: 20px;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            
            .hud-points, .hud-speed {
                background: rgba(0, 0, 0, 0.5);
                padding: 8px 16px;
                border-radius: 15px;
                font-size: 12px;
                color: #FFD700;
            }
            
            .hud-speed {
                color: #4ADE80;
            }
            
            .hud-combo {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: linear-gradient(135deg, #FFD700, #FFA500);
                padding: 15px 30px;
                border-radius: 10px;
                font-size: 24px;
                font-weight: bold;
                color: white;
                text-shadow: 2px 2px 0 #FF6600;
                animation: comboPop 0.5s ease;
            }
            
            @keyframes comboPop {
                0% { transform: translate(-50%, -50%) scale(0); }
                50% { transform: translate(-50%, -50%) scale(1.2); }
                100% { transform: translate(-50%, -50%) scale(1); }
            }
            
            .timer-warning {
                color: #FF6B6B !important;
                animation: timerPulse 0.5s ease infinite;
            }
            
            @keyframes timerPulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.1); }
            }
            
            /* Pause Screen */
            .pause-title {
                font-size: 48px;
                color: #4ADE80;
                margin-bottom: 30px;
            }
            
            .pause-prompt {
                font-size: 16px;
                color: #aaa;
            }
            
            /* Game Over Screen */
            .gameover-title {
                font-size: 36px;
                color: #FF6B6B;
                margin-bottom: 30px;
            }
            
            .gameover-title.victory {
                color: #4ADE80;
            }
            
            .final-stats {
                font-size: 18px;
                color: white;
                line-height: 2;
                margin-bottom: 30px;
            }
            
            .new-best {
                color: #FFD700;
                font-size: 24px;
                animation: newBestPulse 0.5s ease infinite alternate;
            }
            
            @keyframes newBestPulse {
                from { transform: scale(1); }
                to { transform: scale(1.1); }
            }
            
            .restart-prompt {
                font-size: 16px;
                color: #4ADE80;
                animation: blink 1s ease infinite;
            }
            
            /* Coin collected animation */
            .coin-pop {
                animation: coinPop 0.3s ease;
            }
            
            @keyframes coinPop {
                0% { transform: scale(1); }
                50% { transform: scale(1.4); color: #4ADE80; }
                100% { transform: scale(1); }
            }
        `
        document.head.appendChild(style)
    }

    spawnCoins() {
        // Clear existing coins
        this.collectibles.forEach(coin => {
            this.collectibleGroup.remove(coin)
        })
        this.collectibles = []
        
        // Define coin positions based on difficulty
        const coinPositions = this.getCoinPositions()
        
        coinPositions.forEach(pos => {
            this.createCoin(pos.x, pos.z, pos.y || 1.5)
        })
        
        this.totalCoins = this.collectibles.length
        this.updateUI()
    }
    
    getCoinPositions() {
        // Coins positioned around the circular track (radius ~50)
        const positions = []
        const trackRadius = 50
        const numCoinsOnTrack = 24
        
        // Coins around the main track
        for (let i = 0; i < numCoinsOnTrack; i++) {
            const angle = (i / numCoinsOnTrack) * Math.PI * 2
            // Slight variation in radius to make it more interesting
            const radiusVariation = (i % 3 - 1) * 5
            const x = Math.cos(angle) * (trackRadius + radiusVariation)
            const z = Math.sin(angle) * (trackRadius + radiusVariation)
            positions.push({ x, z })
        }
        
        // Extra coins near starting area
        positions.push({ x: 60, z: 0 })
        positions.push({ x: 65, z: 5 })
        positions.push({ x: 65, z: -5 })
        
        // Coins on the inside of the track (bonus/shortcut coins)
        for (let i = 0; i < 8; i++) {
            const angle = (i / 8) * Math.PI * 2
            const x = Math.cos(angle) * 30
            const z = Math.sin(angle) * 30
            positions.push({ x, z })
        }
        
        // A few coins in the very center
        positions.push({ x: 0, z: 0 })
        positions.push({ x: 5, z: 5 })
        positions.push({ x: -5, z: 5 })
        positions.push({ x: 5, z: -5 })
        positions.push({ x: -5, z: -5 })
        
        return positions
    }



    createCoin(x, z, y = 1.5) {
        const coinGroup = new THREE.Group()
        
        // Main coin body - more vibrant gold
        const coinGeometry = new THREE.CylinderGeometry(0.6, 0.6, 0.2, 16)
        const coinMaterial = new THREE.MeshToonMaterial({
            color: 0xFFD700,
            emissive: 0xFFA500,
            emissiveIntensity: 0.4
        })
        const coin = new THREE.Mesh(coinGeometry, coinMaterial)
        coin.rotation.x = Math.PI / 2
        coinGroup.add(coin)
        
        // Star detail in center
        const starGeometry = new THREE.CylinderGeometry(0.25, 0.25, 0.21, 5)
        const starMaterial = new THREE.MeshToonMaterial({
            color: 0xFFFF00,
            emissive: 0xFFFF00,
            emissiveIntensity: 0.3
        })
        const star = new THREE.Mesh(starGeometry, starMaterial)
        star.rotation.x = Math.PI / 2
        coinGroup.add(star)
        
        coinGroup.position.set(x, y, z)
        
        coinGroup.userData = {
            type: 'coin',
            value: this.settings.coinValue,
            collected: false,
            baseY: y
        }
        
        this.collectibleGroup.add(coinGroup)
        this.collectibles.push(coinGroup)
        
        return coinGroup
    }
    
    // Game state methods
    startGame() {
        if (this.state !== 'ready') return
        
        this.state = 'playing'
        this.timeRemaining = this.settings.timeLimit
        this.score = 0
        this.coinsCollected = 0
        this.lastUpdate = Date.now()
        
        // Resume audio context if suspended
        if (this.audioContext?.state === 'suspended') {
            this.audioContext.resume()
        }
        
        // Play start sound
        this.playSound(523, 0.1) // C5
        setTimeout(() => this.playSound(659, 0.1), 100) // E5
        setTimeout(() => this.playSound(784, 0.2), 200) // G5
        
        // Hide start screen, show HUD
        document.getElementById('start-screen').classList.add('hidden')
        document.getElementById('game-hud').classList.remove('hidden')
        
        this.updateUI()
    }
    
    pauseGame() {
        if (this.state !== 'playing') return
        
        this.state = 'paused'
        document.getElementById('pause-screen').classList.remove('hidden')
    }
    
    resumeGame() {
        if (this.state !== 'paused') return
        
        this.state = 'playing'
        this.lastUpdate = Date.now()
        document.getElementById('pause-screen').classList.add('hidden')
    }
    
    gameOver(victory = false) {
        this.state = 'gameOver'
        
        // Play game over sound
        if (victory) {
            this.playSound(784, 0.15) // G5
            setTimeout(() => this.playSound(988, 0.15), 100) // B5
            setTimeout(() => this.playSound(1175, 0.3), 200) // D6
        } else {
            this.playSound(392, 0.2) // G4
            setTimeout(() => this.playSound(330, 0.2), 150) // E4
            setTimeout(() => this.playSound(262, 0.4), 300) // C4
        }
        
        // Update best score
        if (this.score > this.bestScore) {
            this.bestScore = this.score
            this.saveBestScore()
            document.getElementById('new-best').classList.remove('hidden')
        } else {
            document.getElementById('new-best').classList.add('hidden')
        }
        
        // Update game over screen
        const title = document.getElementById('gameover-title')
        if (victory) {
            if (this.currentLap >= this.maxLaps) {
                title.textContent = '🏆 RACE COMPLETE!'
            } else {
                title.textContent = '🏆 ALL COINS COLLECTED!'
            }
            title.classList.add('victory')
        } else {
            title.textContent = "⏰ TIME'S UP!"
            title.classList.remove('victory')
        }
        
        document.getElementById('final-coins').textContent = this.coinsCollected
        document.getElementById('final-laps').textContent = this.currentLap
        document.getElementById('final-score').textContent = this.score
        
        // Show game over screen
        document.getElementById('game-hud').classList.add('hidden')
        document.getElementById('gameover-screen').classList.remove('hidden')
    }
    
    restartGame() {
        // Reset game state
        this.state = 'ready'
        this.score = 0
        this.coinsCollected = 0
        this.timeRemaining = this.settings.timeLimit
        this.lastUpdate = Date.now()
        
        // Reset lap tracking
        this.currentLap = 1
        this.checkpointsPassed = 0
        this.lastCheckpointAngle = 0
        
        // Reset combo
        this.combo = 0
        this.comboTimer = 0
        
        // Respawn coins
        this.spawnCoins()
        
        // Update lap display
        const lapEl = document.getElementById('lap-count')
        if (lapEl) lapEl.textContent = '1'
        
        // Reset UI
        document.getElementById('gameover-screen')?.classList.add('hidden')
        document.getElementById('pause-screen')?.classList.add('hidden')
        document.getElementById('game-hud')?.classList.add('hidden')
        document.getElementById('start-screen')?.classList.remove('hidden')
        document.getElementById('combo-display')?.classList.add('hidden')
        
        const bestScoreEl = document.getElementById('best-score-value')
        if (bestScoreEl) {
            bestScoreEl.textContent = this.bestScore
        }
        
        this.updateUI()
    }

    collectCoin(coin) {
        if (coin.userData.collected || this.state !== 'playing') return
        
        coin.userData.collected = true
        this.coinsCollected++
        
        // Combo system - collect coins quickly for multiplier!
        const now = Date.now()
        if (now - this.lastCoinTime < 1500) {
            this.combo = Math.min(this.combo + 1, 8)
            this.comboTimer = this.comboTimeout
        } else {
            this.combo = 1
            this.comboTimer = this.comboTimeout
        }
        this.lastCoinTime = now
        
        // Score with combo multiplier
        const coinScore = coin.userData.value * Math.max(1, this.combo)
        this.score += coinScore
        
        // Play coin sound (ascending pitch based on combo)
        const pitch = 800 + (this.combo * 100)
        this.playSound(pitch, 0.1)
        
        // Show combo display if combo > 1
        if (this.combo > 1) {
            const comboDisplay = document.getElementById('combo-display')
            const comboCount = document.getElementById('combo-count')
            if (comboDisplay && comboCount) {
                comboCount.textContent = this.combo
                comboDisplay.classList.remove('hidden')
                // Re-trigger animation
                comboDisplay.style.animation = 'none'
                comboDisplay.offsetHeight // Force reflow
                comboDisplay.style.animation = 'comboPop 0.5s ease'
            }
        }
        
        // Update UI with animation
        const coinCount = document.getElementById('coin-count')
        if (coinCount) {
            coinCount.textContent = this.coinsCollected
            coinCount.parentElement.classList.add('coin-pop')
            setTimeout(() => coinCount.parentElement.classList.remove('coin-pop'), 300)
        }
        
        document.getElementById('score-value').textContent = this.score
        
        // Animate coin collection
        this.animateCoinCollection(coin)
        
        // Check for victory - trigger epic celebration!
        if (this.coinsCollected >= this.totalCoins) {
            // Bonus for time remaining
            this.score += Math.floor(this.timeRemaining) * 10
            this.triggerVictoryCelebration()
        }
    }
    
    triggerVictoryCelebration() {
        // Epic fireworks celebration!
        this.fireworks = []
        this.celebrationActive = true
        
        // Play victory fanfare
        const fanfare = [
            { freq: 523, delay: 0 },    // C5
            { freq: 659, delay: 100 },  // E5
            { freq: 784, delay: 200 },  // G5
            { freq: 1047, delay: 300 }, // C6
            { freq: 784, delay: 450 },  // G5
            { freq: 1047, delay: 600 }, // C6
        ]
        fanfare.forEach(note => {
            setTimeout(() => this.playSound(note.freq, 0.2), note.delay)
        })
        
        // Launch fireworks for 3 seconds
        const launchFirework = () => {
            if (!this.celebrationActive) return
            
            const colors = [0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00, 0xFF00FF, 0x00FFFF, 0xFFAA00, 0xFF1493]
            const x = (Math.random() - 0.5) * 80
            const z = (Math.random() - 0.5) * 80
            const color = colors[Math.floor(Math.random() * colors.length)]
            
            this.createFirework(x, z, color)
            this.playSound(200 + Math.random() * 300, 0.05, 'sine')
        }
        
        // Launch multiple fireworks
        for (let i = 0; i < 30; i++) {
            setTimeout(launchFirework, i * 100)
        }
        
        // End celebration and show game over after 3 seconds
        setTimeout(() => {
            this.celebrationActive = false
            this.gameOver(true)
        }, 3000)
    }
    
    createFirework(x, z, color) {
        const particleCount = 30
        const geometry = new THREE.SphereGeometry(0.2, 8, 8)
        const material = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 1
        })
        
        const particles = []
        const startY = 15 + Math.random() * 10
        
        for (let i = 0; i < particleCount; i++) {
            const particle = new THREE.Mesh(geometry, material.clone())
            particle.position.set(x, startY, z)
            
            // Explode in sphere pattern
            const theta = Math.random() * Math.PI * 2
            const phi = Math.random() * Math.PI
            const speed = 0.3 + Math.random() * 0.4
            
            particle.userData = {
                velocity: new THREE.Vector3(
                    Math.sin(phi) * Math.cos(theta) * speed,
                    Math.cos(phi) * speed * 0.5 + 0.2,
                    Math.sin(phi) * Math.sin(theta) * speed
                ),
                life: 1
            }
            
            this.scene.add(particle)
            particles.push(particle)
        }
        
        // Animate firework
        const animate = () => {
            let allDead = true
            
            particles.forEach(p => {
                if (p.userData.life > 0) {
                    allDead = false
                    p.userData.life -= 0.02
                    p.position.add(p.userData.velocity)
                    p.userData.velocity.y -= 0.015 // gravity
                    p.material.opacity = p.userData.life
                    p.scale.setScalar(p.userData.life)
                }
            })
            
            if (!allDead) {
                requestAnimationFrame(animate)
            } else {
                // Cleanup
                particles.forEach(p => {
                    this.scene.remove(p)
                    p.geometry.dispose()
                    p.material.dispose()
                })
            }
        }
        
        animate()
    }

    animateCoinCollection(coin) {
        const startY = coin.position.y
        let progress = 0
        
        const animate = () => {
            progress += 0.08
            
            if (progress < 1) {
                coin.position.y = startY + progress * 3
                coin.scale.setScalar(1 - progress)
                coin.rotation.y += 0.4
                requestAnimationFrame(animate)
            } else {
                this.collectibleGroup.remove(coin)
                const index = this.collectibles.indexOf(coin)
                if (index > -1) this.collectibles.splice(index, 1)
            }
        }
        
        animate()
    }

    checkCollisions(carPosition) {
        if (!carPosition || this.state !== 'playing') return
        
        const carPos = new THREE.Vector3()
        if (carPosition.position) {
            carPos.copy(carPosition.position)
        } else {
            carPos.copy(carPosition)
        }
        
        // Check coin collisions
        this.collectibles.forEach(coin => {
            if (coin.userData.collected) return
            
            const distance = carPos.distanceTo(coin.position)
            if (distance < 2.5) {
                this.collectCoin(coin)
            }
        })
    }
    
    updateUI() {
        const coinCount = document.getElementById('coin-count')
        const totalCoins = document.getElementById('total-coins')
        const scoreValue = document.getElementById('score-value')
        const timeEl = document.getElementById('time-remaining')
        
        if (coinCount) coinCount.textContent = this.coinsCollected
        if (totalCoins) totalCoins.textContent = this.totalCoins
        if (scoreValue) scoreValue.textContent = this.score
        
        if (timeEl) {
            const minutes = Math.floor(this.timeRemaining / 60)
            const seconds = Math.floor(this.timeRemaining % 60)
            timeEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`
            
            // Warning when low on time
            if (this.timeRemaining <= 30) {
                timeEl.parentElement.classList.add('timer-warning')
            } else {
                timeEl.parentElement.classList.remove('timer-warning')
            }
        }
    }
    
    updateSettings(settings) {
        if (settings.coinValue !== undefined) this.settings.coinValue = settings.coinValue
        if (settings.timeLimit !== undefined) {
            this.settings.timeLimit = settings.timeLimit
            if (this.state === 'ready') {
                this.timeRemaining = settings.timeLimit
            }
        }
    }
    
    // Persistence
    loadBestScore() {
        try {
            return parseInt(localStorage.getItem('coinRacerBestScore') || '0')
        } catch {
            return 0
        }
    }
    
    saveBestScore() {
        try {
            localStorage.setItem('coinRacerBestScore', this.bestScore.toString())
        } catch {
            // Storage not available
        }
    }

    update() {
        const now = Date.now()
        const deltaTime = (now - this.lastUpdate) / 1000
        this.lastUpdate = now
        
        // Only update timer when playing
        if (this.state === 'playing') {
            this.timeRemaining -= deltaTime
            
            if (this.timeRemaining <= 0) {
                this.timeRemaining = 0
                this.gameOver(false)
            }
            
            // Update combo timer
            if (this.combo > 0) {
                this.comboTimer -= deltaTime
                if (this.comboTimer <= 0) {
                    this.combo = 0
                    document.getElementById('combo-display')?.classList.add('hidden')
                }
            }
            
            // Update speed display
            this.updateSpeedDisplay()
            
            // Update lap tracking
            this.updateLapTracking()
            
            this.updateUI()
        }
        
        // Animate coins
        const elapsed = this.time.elapsed * 0.001
        
        this.collectibles.forEach(coin => {
            if (coin.userData.collected) return
            
            // Rotate
            coin.rotation.y += 0.03
            
            // Bob up and down
            const bobOffset = Math.sin(elapsed * 3 + coin.position.x * 0.1) * 0.15
            coin.position.y = coin.userData.baseY + bobOffset
        })
        
        // Check coin collisions (only when playing)
        if (this.state === 'playing') {
            const car = this.experience.world?.simpleCar
            if (car?.chassisMesh) {
                this.checkCollisions(car.chassisMesh.position)
            }
        }
    }
    
    updateSpeedDisplay() {
        const car = this.experience.world?.simpleCar
        if (!car?.vehicle?.chassisBody) return
        
        const vel = car.vehicle.chassisBody.velocity
        const speed = Math.sqrt(vel.x * vel.x + vel.z * vel.z)
        const kmh = Math.floor(speed * 10) // Convert to reasonable km/h display
        
        const speedEl = document.getElementById('speed-value')
        if (speedEl) {
            speedEl.textContent = kmh
        }
    }
    
    updateLapTracking() {
        const car = this.experience.world?.simpleCar
        if (!car?.chassisMesh) return
        
        const pos = car.chassisMesh.position

        // Only count laps when crossing the checkered start/finish line
        const withinX = pos.x >= this.startFinish.xMin && pos.x <= this.startFinish.xMax
        const dz = pos.z - this.startFinish.z
        const withinZ = Math.abs(dz) <= this.startFinish.zWindow

        const side = dz >= 0 ? 1 : -1
        if (this.lastStartFinishSide === null) {
            this.lastStartFinishSide = side
            return
        }

        // Crossed the plane at z = startFinish.z
        const crossed = withinX && withinZ && side !== this.lastStartFinishSide
        if (crossed) {
            const now = Date.now()
            if (now - this.lastLapCrossTime >= this.startFinish.cooldownMs) {
                this.lastLapCrossTime = now
                this.completeLap()
            }
        }

        this.lastStartFinishSide = side
    }
    
    completeLap() {
        if (this.currentLap >= this.maxLaps) {
            // All laps complete - trigger victory!
            this.score += this.lapCompleteBonus * 2
            this.triggerVictoryCelebration()
        } else {
            this.currentLap++
            this.score += this.lapCompleteBonus
            
            // Play lap complete sound
            this.playSound(880, 0.1)
            setTimeout(() => this.playSound(1100, 0.15), 100)
            
            // Update UI
            const lapEl = document.getElementById('lap-count')
            if (lapEl) {
                lapEl.textContent = this.currentLap
                lapEl.parentElement.classList.add('coin-pop')
                setTimeout(() => lapEl.parentElement.classList.remove('coin-pop'), 300)
            }
            
            // Respawn coins for new lap
            this.respawnCoinsForNewLap()
        }
    }
    
    respawnCoinsForNewLap() {
        // Re-enable collected coins for the new lap
        this.collectibles.forEach(coin => {
            if (coin.userData.collected) {
                coin.userData.collected = false
                coin.visible = true
                coin.scale.setScalar(1)
            }
        })
        
        this.coinsCollected = 0
        document.getElementById('coin-count').textContent = '0'
    }
}
