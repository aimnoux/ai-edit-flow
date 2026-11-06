/* Example sketch, the 3D layer: two characters made of simple shapes talk, the mouth opens by the word timestamps, the
   camera moves to whoever speaks. No rig, no downloaded models. Colors are style tokens. */
import { RoundedBoxGeometry, THREE, aim, color, drive, mouth, pin, speakerWords, spline, stage, talking, view } from "../../lib/three3d.mjs";

const st = stage({ reach: 4, floor: false, fov: 32, shutter: 0.5 });
const solid = (name, extra = {}) => new THREE.MeshStandardMaterial({ color: color(name), roughness: 0.7, ...extra });
const mesh = (geometry, material, parent, x = 0, y = 0, z = 0) => {
  const m = new THREE.Mesh(geometry, material);
  m.position.set(x, y, z);
  m.castShadow = m.receiveShadow = true;
  parent.add(m);
  return m;
};

// The room: floor, back wall, a desk between the two.
const room = new THREE.Group();
st.scene.add(room);
mesh(new THREE.PlaneGeometry(14, 14), solid("--s1"), room).rotation.x = -Math.PI / 2;
mesh(new THREE.PlaneGeometry(14, 7), solid("--s2"), room, 0, 3.5, -2.6);
mesh(new RoundedBoxGeometry(1.1, 0.1, 0.9, 4, 0.04), solid("--mid"), room, 0, 0.82, 0.25);
for (const x of [-0.45, 0.45]) mesh(new RoundedBoxGeometry(0.08, 0.8, 0.7, 2, 0.03), solid("--mid"), room, x, 0.4, 0.25);

/** A character: rounded body, round head, two eyes, a dark mouth that scales open. */
function character(x, tone, height) {
  const body = new THREE.Group(), head = new THREE.Group();
  body.position.x = x;
  st.scene.add(body);
  mesh(new RoundedBoxGeometry(0.8, height, 0.55, 6, 0.24), solid(tone), body, 0, height / 2, 0);
  head.position.y = height + 0.36;
  body.add(head);
  mesh(new THREE.SphereGeometry(0.36, 48, 32), solid(tone), head);
  for (const side of [-1, 1]) mesh(new THREE.SphereGeometry(0.05, 16, 12), solid("--bg"), head, side * 0.13, 0.07, 0.33);
  const lips = mesh(new THREE.SphereGeometry(0.1, 24, 16), solid("--bg"), head, 0, -0.12, 0.31);
  return { body, head, lips, top: new THREE.Vector3(x, height + 0.82, 0) };
}
const person = (name, x, tone, height) => {
  const words = speakerWords(TM.blocks, name);
  return { ...character(x, tone, height), open: mouth(words), talks: talking(words), side: Math.sign(-x) };
};
const people = { boss: person("boss", -0.95, "--marker", 1.45), dev: person("dev", 0.95, "--fg", 1.25) };

// Camera by the lines: a wide start, then to the speaker of each block, the twist comes closest.
const wide = view(new THREE.Vector3(0, 1.2, 0), 9.5, 0, 8);
const on = (x, dist, az, y = 1.4) => view(new THREE.Vector3(x, y, 0), dist, az, 6);
const cam = spline([
  [0, wide],
  [B("1.1").e, wide],
  [B("1.2").s + 0.4, on(-0.35, 7.6, 0.25)],
  [B("1.3").s + 0.2, on(0.35, 7.2, -0.25)],
  [P("1.3", 1).s, on(0.95, 6.2, -0.3, 2)],
  [D, on(0.95, 5.9, -0.3, 2)],
]);

drive(0, D, (t) => {
  aim(st.camera, cam(t));
  for (const [name, p] of Object.entries(people)) {
    const open = p.open(t), other = name === "boss" ? people.dev : people.boss;
    p.lips.scale.set(1 - 0.25 * open, 0.25 + 1.6 * open, 0.6);
    p.body.position.y = 0.025 * open;                       // the body moves a little with the speech
    p.head.rotation.y = p.side * (0.2 + 0.5 * other.talks(t));   // turns to whoever is speaking
    const label = window.SKETCH_LABELS[name];
    pin(st, label, p.top, -40, -60);
    label.style.opacity = p.talks(t);
  }
  st.renderer.render(st.scene, st.camera);
});
