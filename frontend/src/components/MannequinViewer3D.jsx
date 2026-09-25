import React, { useRef, useEffect, useState, Suspense, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF, Html } from '@react-three/drei';
import * as THREE from 'three';

// ── WebGL Support Checker ───────────────────────────────────────────────────
function checkWebGLSupport() {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch (e) {
    return false;
  }
}

// ── 3D Measurement Rings Component ──────────────────────────────────────────
function MeasurementRings3D({ activeField, rotationAngle }) {
  const bustRingRef = useRef();
  const waistRingRef = useRef();
  const hipRingRef = useRef();
  const heightLineRef = useRef();

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    // Pulse animation for active field ring
    if (activeField === 'bust_cm' && bustRingRef.current) {
      const scale = 1.0 + 0.04 * Math.sin(time * 4);
      bustRingRef.current.scale.set(scale, scale, 1);
    }
    if (activeField === 'waist_cm' && waistRingRef.current) {
      const scale = 1.0 + 0.04 * Math.sin(time * 4);
      waistRingRef.current.scale.set(scale, scale, 1);
    }
    if (activeField === 'hip_cm' && hipRingRef.current) {
      const scale = 1.0 + 0.04 * Math.sin(time * 4);
      hipRingRef.current.scale.set(scale, scale, 1);
    }
  });

  const isBustActive = activeField === 'bust_cm';
  const isWaistActive = activeField === 'waist_cm';
  const isHipActive = activeField === 'hip_cm';
  const isHeightActive = activeField === 'height_cm';

  return (
    <group rotation={[0, -((rotationAngle * Math.PI) / 180), 0]}>
      
      {/* 1. BUST RING (Y = 0.22) */}
      <mesh
        ref={bustRingRef}
        position={[0, 0.22, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <torusGeometry args={[0.205, isBustActive ? 0.009 : 0.004, 16, 64]} />
        <meshStandardMaterial
          color={isBustActive ? "#2D5A43" : "#52B788"}
          emissive={isBustActive ? "#2D5A43" : "#000000"}
          emissiveIntensity={isBustActive ? 0.8 : 0}
          transparent
          opacity={isBustActive ? 1.0 : 0.45}
        />
      </mesh>

      {/* 2. WAIST RING (Y = 0.00) */}
      <mesh
        ref={waistRingRef}
        position={[0, 0.00, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <torusGeometry args={[0.145, isWaistActive ? 0.009 : 0.004, 16, 64]} />
        <meshStandardMaterial
          color={isWaistActive ? "#52B788" : "#74C69D"}
          emissive={isWaistActive ? "#52B788" : "#000000"}
          emissiveIntensity={isWaistActive ? 0.8 : 0}
          transparent
          opacity={isWaistActive ? 1.0 : 0.45}
        />
      </mesh>

      {/* 3. HIP RING (Y = -0.24) */}
      <mesh
        ref={hipRingRef}
        position={[0, -0.24, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <torusGeometry args={[0.195, isHipActive ? 0.009 : 0.004, 16, 64]} />
        <meshStandardMaterial
          color={isHipActive ? "#74C69D" : "#2D6A4F"}
          emissive={isHipActive ? "#74C69D" : "#000000"}
          emissiveIntensity={isHipActive ? 0.8 : 0}
          transparent
          opacity={isHipActive ? 1.0 : 0.45}
        />
      </mesh>

      {/* 4. HEIGHT VERTICAL MEASUREMENT LINE */}
      <group position={[-0.32, 0, 0]}>
        <line ref={heightLineRef}>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              self.setFromPoints([
                new THREE.Vector3(0, 0.84, 0),
                new THREE.Vector3(0, -1.30, 0)
              ]);
            }}
          />
          <lineDashedMaterial
            attach="material"
            color={isHeightActive ? "#2D5A43" : "#74C69D"}
            linewidth={2}
            dashSize={0.05}
            gapSize={0.03}
            transparent
            opacity={isHeightActive ? 1.0 : 0.35}
          />
        </line>
        {/* Top/Bottom Height Caps */}
        <mesh position={[0, 0.84, 0]}>
          <boxGeometry args={[0.08, 0.008, 0.008]} />
          <meshBasicMaterial color={isHeightActive ? "#2D5A43" : "#74C69D"} />
        </mesh>
        <mesh position={[0, -1.30, 0]}>
          <boxGeometry args={[0.08, 0.008, 0.008]} />
          <meshBasicMaterial color={isHeightActive ? "#2D5A43" : "#74C69D"} />
        </mesh>
      </group>

    </group>
  );
}

// ── Mannequin GLTF Model Mesh Component ─────────────────────────────────────
function MannequinModel({ modelPath, rotationAngle, onRotate }) {
  const groupRef = useRef();
  const { scene } = useGLTF(modelPath);

  // Synchronize 3D model rotation.y with slider rotationAngle (degrees to radians)
  useEffect(() => {
    if (groupRef.current && groupRef.current.rotation) {
      groupRef.current.rotation.y = -((rotationAngle * Math.PI) / 180);
    }
  }, [rotationAngle]);

  return (
    <group ref={groupRef} position={[0, 0.15, 0]}>
      <primitive object={scene} />
    </group>
  );
}

// ── OrbitControls Handler with Angle Feedback ───────────────────────────────
function ControlledOrbitControls({ rotationAngle, onAngleChange, isAutoSpinning }) {
  const controlsRef = useRef();

  useFrame(() => {
    if (controlsRef.current && !isAutoSpinning) {
      // Calculate current azimuth angle from OrbitControls camera rotation
      const azimuth = controlsRef.current.getAzimuthalAngle();
      let deg = Math.round((-azimuth * 180) / Math.PI) % 360;
      if (deg < 0) deg += 360;
      
      // Update parent slider if user is dragging with mouse/touch
      if (controlsRef.current.state !== -1 && Math.abs(deg - rotationAngle) > 2) {
        onAngleChange(deg);
      }
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enablePan={false}
      minDistance={1.8}
      maxDistance={4.8}
      minPolarAngle={Math.PI / 4}
      maxPolarAngle={Math.PI / 1.75}
      enableDamping={true}
      dampingFactor={0.08}
    />
  );
}

// ── Loading Fallback Component ──────────────────────────────────────────────
function ModelLoadingFallback() {
  return (
    <Html center>
      <div style={{
        color: '#52B788',
        fontSize: '12px',
        fontWeight: '600',
        background: 'rgba(15, 23, 42, 0.9)',
        padding: '8px 14px',
        borderRadius: '8px',
        border: '1px solid #2D5A43',
        whiteSpace: 'nowrap'
      }}>
        Loading 3D Female Mannequin Model...
      </div>
    </Html>
  );
}

// ── Error Boundary Class Component ──────────────────────────────────────────
class ModelErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMsg: '' };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, errorMsg: error.message || 'Error loading 3D GLB model.' };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px',
          textAlign: 'center',
          color: '#FECACA',
          background: '#1E1E1E',
          fontSize: '12px'
        }}>
          <span style={{ color: '#F87171', fontWeight: 'bold', marginBottom: '6px' }}>3D Model Asset Error</span>
          <span>{this.state.errorMsg}</span>
          <span style={{ fontSize: '11px', color: '#94A3B8', marginTop: '8px' }}>
            Path: /models/female-mannequin.glb
          </span>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Main MannequinViewer3D Exported Component ───────────────────────────────
export default function MannequinViewer3D({
  activeField,
  rotationAngle,
  onAngleChange,
  isAutoSpinning,
  modelPath = '/models/female-mannequin.glb'
}) {
  const [webGLSupported, setWebGLSupported] = useState(true);

  useEffect(() => {
    setWebGLSupported(checkWebGLSupport());
  }, []);

  if (!webGLSupported) {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        textAlign: 'center',
        background: '#0F172A',
        color: '#94A3B8',
        fontSize: '12px',
        borderRadius: '12px',
        border: '1px solid #1E293B'
      }}>
        <strong style={{ color: '#F87171', fontSize: '13px', marginBottom: '6px' }}>
          WebGL Hardware Acceleration Unavailable
        </strong>
        <span>
          Your browser or GPU environment does not support WebGL rendering. Real-time interactive 3D graphics require WebGL.
        </span>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      <ModelErrorBoundary>
        <Canvas
          camera={{ position: [0, 0.1, 3.2], fov: 45 }}
          shadows
          style={{ width: '100%', height: '100%', background: 'transparent' }}
          gl={{ antialias: true, alpha: true }}
        >
          {/* Studio Lighting Setup */}
          <ambientLight intensity={0.95} />
          <directionalLight position={[3, 4, 3]} intensity={1.3} castShadow />
          <directionalLight position={[-3, 2, -2]} intensity={0.6} color="#A7F3D0" />
          <pointLight position={[0, 2.8, 0]} intensity={0.5} />

          <Suspense fallback={<ModelLoadingFallback />}>
            <MannequinModel
              modelPath={modelPath}
              rotationAngle={rotationAngle}
              onRotate={onAngleChange}
            />
            <MeasurementRings3D
              activeField={activeField}
              rotationAngle={rotationAngle}
            />
          </Suspense>

          <ControlledOrbitControls
            rotationAngle={rotationAngle}
            onAngleChange={onAngleChange}
            isAutoSpinning={isAutoSpinning}
          />
        </Canvas>
      </ModelErrorBoundary>
    </div>
  );
}

// Preload female mannequin model asset
try {
  useGLTF.preload('/models/female-mannequin.glb');
} catch (e) {
  // Preload fallback
}
