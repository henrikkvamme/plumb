import {
  Mesh,
  MeshBasicMaterial,
  OrthographicCamera,
  Plane,
  PlaneGeometry,
  Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  WebGLRenderTarget,
} from "three";
import type { Box3, Object3D, Texture, WebGLRenderer } from "three";

export interface ContactShadow {
  readonly dispose: () => void;
  readonly mesh: Mesh;
}

const resolution = 512;

const bakeLayer = 1;

const blurVertex = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const blurFragment = /* glsl */ `
uniform sampler2D map;
uniform vec2 direction;
varying vec2 vUv;
void main() {
  vec4 sum = texture2D(map, vUv) * 0.1964825501511404;
  sum += texture2D(map, vUv + direction * 1.411764705882353) * 0.2969069646728344;
  sum += texture2D(map, vUv - direction * 1.411764705882353) * 0.2969069646728344;
  sum += texture2D(map, vUv + direction * 3.2941176470588234) * 0.09447039785044732;
  sum += texture2D(map, vUv - direction * 3.2941176470588234) * 0.09447039785044732;
  sum += texture2D(map, vUv + direction * 5.176470588235294) * 0.010381362401148057;
  sum += texture2D(map, vUv - direction * 5.176470588235294) * 0.010381362401148057;
  gl_FragColor = sum;
}
`;

export const markForShadow = (object: Object3D) => {
  object.layers.enable(bakeLayer);
};

export const bakeContactShadow = (
  renderer: WebGLRenderer,
  scene: Scene,
  bounds: Box3,
  opacity: number,
): ContactShadow => {
  const size = bounds.getSize(new Vector3());
  const margin = Math.max(size.x, size.z) * 0.18 + 1;
  const halfX = size.x / 2 + margin;
  const halfZ = size.z / 2 + margin;
  const centre = bounds.getCenter(new Vector3());
  const ground = bounds.min.y;
  const camera = new OrthographicCamera(-halfX, halfX, halfZ, -halfZ, 0.01, size.y + 2);

  camera.position.set(centre.x, bounds.max.y + 1, centre.z);
  camera.up.set(0, 0, -1);
  camera.lookAt(centre.x, ground, centre.z);
  camera.layers.set(bakeLayer);

  const silhouette = new WebGLRenderTarget(resolution, resolution);
  const spare = new WebGLRenderTarget(resolution, resolution);

  const ink = new MeshBasicMaterial({
    clippingPlanes: [new Plane(new Vector3(0, -1, 0), ground + 1.4)],
    color: "#000000",
  });

  const mapUniform = { value: silhouette.texture };
  const directionUniform = { value: new Vector2() };

  const blur = new ShaderMaterial({
    depthTest: false,
    depthWrite: false,
    fragmentShader: blurFragment,
    toneMapped: false,
    uniforms: { direction: directionUniform, map: mapUniform },
    vertexShader: blurVertex,
  });

  const quadGeometry = new PlaneGeometry(2, 2);
  const quadScene = new Scene();

  const quad = new Mesh(quadGeometry, blur);
  const quadCamera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);

  quad.frustumCulled = false;
  quadScene.add(quad);

  const previousTarget = renderer.getRenderTarget();
  const previousOverride = scene.overrideMaterial;

  renderer.setRenderTarget(silhouette);
  renderer.clear();
  scene.overrideMaterial = ink;
  renderer.render(scene, camera);
  scene.overrideMaterial = previousOverride;

  const pass = (from: Texture, to: WebGLRenderTarget, x: number, y: number) => {
    mapUniform.value = from;
    directionUniform.value.set(x / resolution, y / resolution);
    renderer.setRenderTarget(to);
    renderer.clear();
    renderer.render(quadScene, quadCamera);
  };

  for (const spread of [2.2, 1.4]) {
    pass(silhouette.texture, spare, spread, 0);
    pass(spare.texture, silhouette, 0, spread);
  }

  renderer.setRenderTarget(previousTarget);
  spare.dispose();
  quadGeometry.dispose();
  blur.dispose();
  ink.dispose();

  const geometry = new PlaneGeometry(halfX * 2, halfZ * 2);

  const material = new MeshBasicMaterial({
    color: "#000000",
    depthWrite: false,
    map: silhouette.texture,
    opacity,
    transparent: true,
  });

  const mesh = new Mesh(geometry, material);

  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(centre.x, ground + 0.001, centre.z);
  mesh.renderOrder = -1;

  return {
    dispose: () => {
      geometry.dispose();
      material.dispose();
      silhouette.dispose();
    },
    mesh,
  };
};
