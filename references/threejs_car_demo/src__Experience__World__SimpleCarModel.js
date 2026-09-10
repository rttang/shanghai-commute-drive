import * as THREE from 'three'
import Experience from '../Experience.js'

export default class SimpleCarModel {
    constructor() {
        this.experience = new Experience()
        this.scene = this.experience.scene

        // Nintendo-style vibrant colors
        this.nintendoColors = [
            0xFF0000, // Mario Red
            0x00AA00, // Luigi Green
            0x0066FF, // Toad Blue
            0xFFDD00, // Wario Yellow
            0xFF66AA, // Peach Pink
            0xFF6600  // DK Orange
        ]
        
        this.currentColorIndex = 0

        this.setModel()
    }

    setModel() {
        const color = this.nintendoColors[this.currentColorIndex]
        
        // Main chassis group
        this.chassisMesh = new THREE.Group()
        this.chassisMesh.position.set(5, 5, 0)

        // === KART BODY ===
        // Clean, cohesive kart silhouette (less busy)
        const bodyGeometry = new THREE.BoxGeometry(1.9, 0.6, 3.2)
        const bodyMaterial = new THREE.MeshToonMaterial({ color })
        const bodyMesh = new THREE.Mesh(bodyGeometry, bodyMaterial)
        bodyMesh.position.y = 0.25
        bodyMesh.castShadow = true
        this.chassisMesh.add(bodyMesh)

        // Nose / front fairing
        const noseGeometry = new THREE.BoxGeometry(1.5, 0.45, 0.8)
        const noseMesh = new THREE.Mesh(noseGeometry, bodyMaterial)
        noseMesh.position.set(0, 0.12, 1.9)
        noseMesh.castShadow = true
        this.chassisMesh.add(noseMesh)

        // Front bumper (dark)
        const bumperGeometry = new THREE.BoxGeometry(1.8, 0.22, 0.25)
        const bumperMaterial = new THREE.MeshToonMaterial({ color: 0x1a1a1a })
        const bumper = new THREE.Mesh(bumperGeometry, bumperMaterial)
        bumper.position.set(0, 0.05, 2.2)
        bumper.castShadow = true
        this.chassisMesh.add(bumper)

        // Cockpit top
        const cockpitGeometry = new THREE.BoxGeometry(1.35, 0.35, 1.5)
        const cockpitMaterial = new THREE.MeshToonMaterial({ color: 0x222222 })
        const cockpit = new THREE.Mesh(cockpitGeometry, cockpitMaterial)
        cockpit.position.set(0, 0.62, -0.15)
        cockpit.castShadow = true
        this.chassisMesh.add(cockpit)

        // Simple rear engine block
        const engineGeometry = new THREE.BoxGeometry(1.1, 0.28, 0.55)
        const engineMaterial = new THREE.MeshToonMaterial({ color: 0x333333 })
        const engine = new THREE.Mesh(engineGeometry, engineMaterial)
        engine.position.set(0, 0.18, -1.75)
        engine.castShadow = true
        this.chassisMesh.add(engine)
        
        // Rear spoiler holder
        const spoilerHolderGeo = new THREE.BoxGeometry(0.15, 0.6, 0.15)
        const spoilerMat = new THREE.MeshToonMaterial({ color: 0x333333 })
        const spoilerLeft = new THREE.Mesh(spoilerHolderGeo, spoilerMat)
        spoilerLeft.position.set(-0.6, 0.5, -1.4)
        this.chassisMesh.add(spoilerLeft)
        
        const spoilerRight = new THREE.Mesh(spoilerHolderGeo, spoilerMat)
        spoilerRight.position.set(0.6, 0.5, -1.4)
        this.chassisMesh.add(spoilerRight)
        
        // Spoiler wing
        const wingGeometry = new THREE.BoxGeometry(1.6, 0.1, 0.45)
        const wingMaterial = new THREE.MeshToonMaterial({ color: color })
        const wing = new THREE.Mesh(wingGeometry, wingMaterial)
        wing.position.set(0, 0.85, -1.95)
        wing.castShadow = true
        this.chassisMesh.add(wing)
        
        // Driver seat (simple representation)
        const seatGeometry = new THREE.BoxGeometry(0.8, 0.4, 0.6)
        const seatMaterial = new THREE.MeshToonMaterial({ color: 0x222222 })
        const seat = new THREE.Mesh(seatGeometry, seatMaterial)
        seat.position.set(0, 0.5, -0.2)
        this.chassisMesh.add(seat)
        
        // Steering wheel
        const steeringGeometry = new THREE.TorusGeometry(0.15, 0.03, 8, 16)
        const steeringMaterial = new THREE.MeshToonMaterial({ color: 0x333333 })
        const steering = new THREE.Mesh(steeringGeometry, steeringMaterial)
        steering.position.set(0, 0.6, 0.4)
        steering.rotation.x = -Math.PI * 0.3
        this.chassisMesh.add(steering)
        
        // Headlights - brighter and more prominent
        const lightGeometry = new THREE.CircleGeometry(0.15, 16)
        const lightMaterial = new THREE.MeshToonMaterial({ 
            color: 0xFFFACD,
            emissive: 0xFFD700,
            emissiveIntensity: 0.6
        })
        
        const headlightL = new THREE.Mesh(lightGeometry, lightMaterial)
        headlightL.position.set(-0.5, 0.15, 2.25)
        this.chassisMesh.add(headlightL)
        
        const headlightR = new THREE.Mesh(lightGeometry, lightMaterial)
        headlightR.position.set(0.5, 0.15, 2.25)
        this.chassisMesh.add(headlightR)
        
        // Headlight rings for depth
        const ringGeometry = new THREE.TorusGeometry(0.16, 0.03, 8, 16)
        const ringMaterial = new THREE.MeshToonMaterial({ color: 0x444444 })
        const ringL = new THREE.Mesh(ringGeometry, ringMaterial)
        ringL.position.set(-0.5, 0.15, 2.24)
        ringL.rotation.y = Math.PI / 2
        this.chassisMesh.add(ringL)
        const ringR = new THREE.Mesh(ringGeometry, ringMaterial)
        ringR.position.set(0.5, 0.15, 2.24)
        ringR.rotation.y = Math.PI / 2
        this.chassisMesh.add(ringR)
        
        // === WHEELS ===
        // Wheel positions - matching physics, further from chassis
        const wheelPositions = {
            frontLeft: { x: 1.3, y: -0.2, z: 1.5 },
            frontRight: { x: -1.3, y: -0.2, z: 1.5 },
            rearLeft: { x: 1.3, y: -0.2, z: -1.3 },
            rearRight: { x: -1.3, y: -0.2, z: -1.3 }
        }
        
        // All wheels same size (0.5 radius to match physics spheres)
        this.frontWheelMesh1 = this.createKartWheel(0.55, 0.45, color)
        this.frontWheelMesh1.position.set(
            5 + wheelPositions.frontLeft.x,
            5 + wheelPositions.frontLeft.y,
            wheelPositions.frontLeft.z
        )

        this.frontWheelMesh2 = this.createKartWheel(0.55, 0.45, color)
        this.frontWheelMesh2.position.set(
            5 + wheelPositions.frontRight.x,
            5 + wheelPositions.frontRight.y,
            wheelPositions.frontRight.z
        )

        // Rear wheels (same size as front)
        this.rearWheelMesh1 = this.createKartWheel(0.55, 0.45, color)
        this.rearWheelMesh1.position.set(
            5 + wheelPositions.rearLeft.x,
            5 + wheelPositions.rearLeft.y,
            wheelPositions.rearLeft.z
        )

        this.rearWheelMesh2 = this.createKartWheel(0.55, 0.45, color)
        this.rearWheelMesh2.position.set(
            5 + wheelPositions.rearRight.x,
            5 + wheelPositions.rearRight.y,
            wheelPositions.rearRight.z
        )
        
        // Store body material for color changes
        this.bodyMaterial = bodyMaterial
        this.wingMaterial = wingMaterial
    }

    createKartWheel(radius, width, accentColor) {
        const wheelGroup = new THREE.Group()

        // Tire (black rubber with shine)
        const tireGeometry = new THREE.CylinderGeometry(radius, radius, width, 32)
        const tireMaterial = new THREE.MeshToonMaterial({
            color: 0x0a0a0a,
            emissive: 0x1a1a1a
        })
        const tire = new THREE.Mesh(tireGeometry, tireMaterial)
        tire.castShadow = true
        wheelGroup.add(tire)

        // Rim (metallic with accent color)
        const rimGeometry = new THREE.CylinderGeometry(radius * 0.65, radius * 0.65, width + 0.05, 16)
        const rimMaterial = new THREE.MeshToonMaterial({
            color: 0xCCCCCC,
            emissive: accentColor,
            emissiveIntensity: 0.3
        })
        const rim = new THREE.Mesh(rimGeometry, rimMaterial)
        rim.position.z = 0.01
        wheelGroup.add(rim)

        // Spokes/lugs for detail
        for (let i = 0; i < 5; i++) {
            const spokeGeometry = new THREE.BoxGeometry(0.08, radius * 0.4, 0.04)
            const spokeMaterial = new THREE.MeshToonMaterial({ color: accentColor })
            const spoke = new THREE.Mesh(spokeGeometry, spokeMaterial)
            spoke.rotation.z = (i / 5) * Math.PI * 2
            rim.add(spoke)
        }

        // Center hub
        const hubGeometry = new THREE.CylinderGeometry(radius * 0.2, radius * 0.2, width + 0.1, 16)
        const hubMaterial = new THREE.MeshToonMaterial({ color: accentColor })
        const hub = new THREE.Mesh(hubGeometry, hubMaterial)
        wheelGroup.add(hub)

        return wheelGroup
    }

    updateMeshPosition(mesh, body) {
        mesh.position.copy(body.position)

        if (mesh === this.frontWheelMesh1 ||
            mesh === this.frontWheelMesh2 ||
            mesh === this.rearWheelMesh1 ||
            mesh === this.rearWheelMesh2) {

            mesh.rotation.set(0, 0, Math.PI / 2)

            const bodyQuat = new THREE.Quaternion(
                body.quaternion.x,
                body.quaternion.y,
                body.quaternion.z,
                body.quaternion.w
            )

            mesh.quaternion.premultiply(bodyQuat)
        } else {
            mesh.quaternion.copy(body.quaternion)
        }
    }
    
    // Change car color
    setColor(color) {
        if (this.bodyMaterial) {
            this.bodyMaterial.color.set(color)
        }
        if (this.wingMaterial) {
            this.wingMaterial.color.set(color)
        }
    }
    
    // Cycle through colors
    cycleColor() {
        this.currentColorIndex = (this.currentColorIndex + 1) % this.nintendoColors.length
        this.setColor(this.nintendoColors[this.currentColorIndex])
        return this.nintendoColors[this.currentColorIndex]
    }

    getNintendoColors() {
        return this.nintendoColors
    }
}
