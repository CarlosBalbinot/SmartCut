#!/usr/bin/env node
/**
 * svgnest_headless.js — SVGnest (Jack Qiao, MIT) rodando sem navegador.
 *
 * Reaproveita, sem alterar, os arquivos vendorizados em
 * backend/nesting/svgnest/util (clipper.js, geometryutil.js, matrix.js,
 * placementworker.js). O laço do algoritmo genético e o cálculo de NFP são
 * uma cópia de svgnest.js (launchWorkers / GeneticAlgorithm) sem DOM e sem
 * Web Workers, com duas mudanças:
 *   - randomAngle escolhe entre as rotações permitidas de cada peça (fio),
 *     em vez de N ângulos igualmente espaçados;
 *   - cache de NFP por FORMA (molde + rotação), não por instância — cópias
 *     da mesma peça compartilham o NFP (mesmo resultado, bem menos cálculo).
 *
 * Entrada (stdin, JSON):
 *   { bin: {length, width},            // cm; o SVGnest comprime o eixo "length"
 *     parts: [{id, polygon:[[x,y]...], quantity, rotations:[0,180]}],
 *     config: {populationSize, mutationRate, generations, timeLimitSec,
 *              curveTolerance, seed} }
 *   Polígonos no referencial do SmartCut: x = largura do tecido, y = comprimento.
 *
 * Saída (stdout, JSON):
 *   { bins: [[{id, rotation, points:[[x,y]...]}]],  // mesmo referencial da entrada
 *     fitness, generations, evaluations, seconds }
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SVGNEST = path.resolve(__dirname, '..', '..', 'nesting', 'svgnest', 'util');

// ── PRNG com semente (o GA usa Math.random) ─────────────────────────────────
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Carrega as libs do SVGnest no escopo global ─────────────────────────────
globalThis.window = globalThis;
globalThis.self = globalThis;
for (const f of ['clipper.js', 'matrix.js', 'geometryutil.js', 'placementworker.js']) {
  vm.runInThisContext(fs.readFileSync(path.join(SVGNEST, f), 'utf8'), { filename: f });
}
const { GeometryUtil, ClipperLib, PlacementWorker } = globalThis;

let MINK_SCALE = 10000000; // svgnest.js usa 1e7 fixo
let SANEAR_NFP = true;

// ── NFP (cópia do p.map de svgnest.js, exploreConcave=false, sem furos) ─────
function minkowskiDifference(A, B) {
  const Ac = A.map(p => ({ X: p.x, Y: p.y }));
  ClipperLib.JS.ScaleUpPath(Ac, MINK_SCALE);
  const Bc = B.map(p => ({ X: -p.x, Y: -p.y }));
  ClipperLib.JS.ScaleUpPath(Bc, MINK_SCALE);
  const solution = ClipperLib.Clipper.MinkowskiSum(Ac, Bc, true);
  let clipperNfp = null, largestArea = null;
  for (const s of solution) {
    const n = s.map(p => ({ x: p.X / MINK_SCALE, y: p.Y / MINK_SCALE }));
    const sarea = GeometryUtil.polygonArea(n);
    if (largestArea === null || largestArea > sarea) { clipperNfp = n; largestArea = sarea; }
  }
  // CORREÇÃO (não existe no svgnest.js): com peças côncavas (perna de
  // legging) o anel devolvido pelo MinkowskiSum sai auto-intersectante e
  // alguns vértices deixam a peça B penetrar A (até 12 cm² medidos no
  // COSTAS M 0°×180°). SimplifyPolygon NonZero saneia o anel.
  if (SANEAR_NFP) {
    const P = clipperNfp.map(q => ({ X: q.x * MINK_SCALE, Y: q.y * MINK_SCALE }));
    const S = ClipperLib.Clipper.SimplifyPolygon(P, ClipperLib.PolyFillType.pftNonZero);
    let bg = S[0];
    for (const s of S) if (Math.abs(ClipperLib.Clipper.Area(s)) > Math.abs(ClipperLib.Clipper.Area(bg))) bg = s;
    clipperNfp = bg.map(q => ({ x: q.X / MINK_SCALE, y: q.Y / MINK_SCALE }));
  }
  for (const p of clipperNfp) { p.x += B[0].x; p.y += B[0].y; }
  return [clipperNfp];
}

function computeNfp(A0, B0, Arot, Brot, inside) {
  const A = rotatePolygon(A0, Arot);
  const B = rotatePolygon(B0, Brot);
  let nfp;
  if (inside) {
    nfp = GeometryUtil.isRectangle(A, 0.001)
      ? GeometryUtil.noFitPolygonRectangle(A, B)
      : GeometryUtil.noFitPolygon(A, B, true, false);
    if (nfp && nfp.length) for (const n of nfp) if (GeometryUtil.polygonArea(n) > 0) n.reverse();
    return nfp && nfp.length ? nfp : null;
  }
  nfp = minkowskiDifference(A, B);
  if (!nfp || !nfp.length) return null;
  if (Math.abs(GeometryUtil.polygonArea(nfp[0])) < Math.abs(GeometryUtil.polygonArea(A))) return null;
  for (let i = 0; i < nfp.length; i++) {
    if (GeometryUtil.polygonArea(nfp[i]) > 0) nfp[i].reverse();
    if (i > 0 && GeometryUtil.pointInPolygon(nfp[i][0], nfp[0]) && GeometryUtil.polygonArea(nfp[i]) < 0) nfp[i].reverse();
  }
  return nfp;
}

// ── GeneticAlgorithm (cópia de svgnest.js; randomAngle por peça) ───────────
function GeneticAlgorithm(adam, bin, config) {
  this.config = config;
  this.binBounds = GeometryUtil.getPolygonBounds(bin);
  const angles = adam.map(p => this.randomAngle(p));
  this.population = [{ placement: adam, rotation: angles }];
  while (this.population.length < config.populationSize) this.population.push(this.mutate(this.population[0]));
}
GeneticAlgorithm.prototype.randomAngle = function (part) {
  const angleList = part.allowed.slice(0);
  for (let i = angleList.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [angleList[i], angleList[j]] = [angleList[j], angleList[i]];
  }
  for (const a of angleList) {
    const r = GeometryUtil.rotatePolygon(part, a);
    if (r.width < this.binBounds.width && r.height < this.binBounds.height) return a;
  }
  return angleList[0];
};
GeneticAlgorithm.prototype.mutate = function (individual) {
  const clone = { placement: individual.placement.slice(0), rotation: individual.rotation.slice(0) };
  for (let i = 0; i < clone.placement.length; i++) {
    if (Math.random() < 0.01 * this.config.mutationRate) {
      const j = i + 1;
      if (j < clone.placement.length) {
        [clone.placement[i], clone.placement[j]] = [clone.placement[j], clone.placement[i]];
        // (svgnest original não troca a rotação junto — mantido)
      }
    }
    if (Math.random() < 0.01 * this.config.mutationRate) clone.rotation[i] = this.randomAngle(clone.placement[i]);
  }
  return clone;
};
GeneticAlgorithm.prototype.mate = function (male, female) {
  const cutpoint = Math.round(Math.min(Math.max(Math.random(), 0.1), 0.9) * (male.placement.length - 1));
  const gene1 = male.placement.slice(0, cutpoint), rot1 = male.rotation.slice(0, cutpoint);
  const gene2 = female.placement.slice(0, cutpoint), rot2 = female.rotation.slice(0, cutpoint);
  const contains = (gene, id) => gene.some(g => g.id == id);
  for (let i = 0; i < female.placement.length; i++) if (!contains(gene1, female.placement[i].id)) { gene1.push(female.placement[i]); rot1.push(female.rotation[i]); }
  for (let i = 0; i < male.placement.length; i++) if (!contains(gene2, male.placement[i].id)) { gene2.push(male.placement[i]); rot2.push(male.rotation[i]); }
  return [{ placement: gene1, rotation: rot1 }, { placement: gene2, rotation: rot2 }];
};
GeneticAlgorithm.prototype.generation = function () {
  this.population.sort((a, b) => a.fitness - b.fitness);
  const np = [this.population[0]];
  while (np.length < this.population.length) {
    const male = this.randomWeightedIndividual();
    const female = this.randomWeightedIndividual(male);
    const children = this.mate(male, female);
    np.push(this.mutate(children[0]));
    if (np.length < this.population.length) np.push(this.mutate(children[1]));
  }
  this.population = np;
};
GeneticAlgorithm.prototype.randomWeightedIndividual = function (exclude) {
  const pop = this.population.slice(0);
  if (exclude && pop.indexOf(exclude) >= 0) pop.splice(pop.indexOf(exclude), 1);
  const rand = Math.random();
  let lower = 0; const weight = 1 / pop.length; let upper = weight;
  for (let i = 0; i < pop.length; i++) {
    if (rand > lower && rand < upper) return pop[i];
    lower = upper; upper += 2 * weight * ((pop.length - i) / pop.length);
  }
  return pop[0];
};

// ── Limpeza do polígono (cleanPolygon de svgnest.js) ────────────────────────
function cleanPolygon(poly, curveTolerance, scale) {
  const p = poly.map(q => ({ X: q.x, Y: q.y }));
  ClipperLib.JS.ScaleUpPath(p, scale);
  const simple = ClipperLib.Clipper.SimplifyPolygon(p, ClipperLib.PolyFillType.pftNonZero);
  if (!simple || !simple.length) return null;
  let biggest = simple[0], ba = Math.abs(ClipperLib.Clipper.Area(biggest));
  for (const s of simple.slice(1)) { const a = Math.abs(ClipperLib.Clipper.Area(s)); if (a > ba) { biggest = s; ba = a; } }
  const clean = ClipperLib.Clipper.CleanPolygon(biggest, curveTolerance * scale);
  return clean && clean.length ? clean.map(q => ({ x: q.X / scale, y: q.Y / scale })) : null;
}

// Offset externo (polygonOffset de svgnest.js, usado lá para o spacing): a
// simplificação corta as curvas por dentro; inflar pela mesma tolerância
// garante que o contorno real nunca sobreponha.
function offsetPolygon(poly, offset, cfg) {
  const p = poly.map(q => ({ X: q.x, Y: q.y }));
  ClipperLib.JS.ScaleUpPath(p, cfg.clipperScale);
  const co = new ClipperLib.ClipperOffset(2, cfg.curveTolerance * cfg.clipperScale);
  co.AddPath(p, ClipperLib.JoinType.jtRound, ClipperLib.EndType.etClosedPolygon);
  const out = new ClipperLib.Paths();
  co.Execute(out, offset * cfg.clipperScale);
  return out[0].map(q => ({ x: q.X / cfg.clipperScale, y: q.Y / cfg.clipperScale }));
}

// ── Execução ────────────────────────────────────────────────────────────────
function run(input) {
  const cfg = Object.assign({
    clipperScale: 10000000, curveTolerance: 0.3, spacing: 0, populationSize: 10, mutationRate: 10,
    generations: 0, timeLimitSec: 10, seed: 1, inflate: 0, sanearNfp: true, useHoles: false, exploreConcave: false,
  }, input.config || {});
  Math.random = mulberry32(cfg.seed);
  MINK_SCALE = cfg.clipperScale;
  SANEAR_NFP = cfg.sanearNfp;

  // Troca de eixos (x↔y): o SVGnest comprime o eixo x; no SmartCut o
  // comprimento é y. Reflexão é a própria inversa, e 0°/180° são invariantes.
  const swap = pts => pts.map(p => ({ x: p.y, y: p.x }));

  const L = input.bin.length, W = input.bin.width;
  const binPolygon = [{ x: 0, y: 0 }, { x: L, y: 0 }, { x: L, y: W }, { x: 0, y: W }];
  if (GeometryUtil.polygonArea(binPolygon) > 0) binPolygon.reverse();
  binPolygon.id = -1;

  // formas (molde) e instâncias (cópias)
  const shapes = [];
  const tree = [];
  for (const part of input.parts) {
    let poly = swap(part.polygon.map(([x, y]) => ({ x, y })));
    const a = poly[0], b = poly[poly.length - 1];
    if (GeometryUtil.almostEqual(a.x, b.x) && GeometryUtil.almostEqual(a.y, b.y)) poly.pop();
    const orig = poly.map(p => ({ ...p }));
    poly = cleanPolygon(poly, cfg.curveTolerance, cfg.clipperScale);
    if (cfg.inflate > 0) poly = offsetPolygon(poly, cfg.inflate, cfg);
    if (GeometryUtil.polygonArea(poly) > 0) poly.reverse();
    const sid = shapes.length;
    shapes.push({ id: part.id, poly, orig });
    for (let q = 0; q < part.quantity; q++) {
      const inst = poly.map(p => ({ ...p }));
      inst.id = tree.length; inst.shape = sid; inst.allowed = part.rotations && part.rotations.length ? part.rotations : [0];
      tree.push(inst);
    }
  }

  // cache de NFP por forma, exposto ao PlacementWorker com as chaves por instância
  const shapeCache = new Map();
  const nfpFor = (keyStr) => {
    const k = JSON.parse(keyStr);
    const sA = k.A === -1 ? -1 : tree[k.A].shape, sB = tree[k.B].shape;
    const sk = `${sA}|${sB}|${k.inside}|${k.Arotation}|${k.Brotation}`;
    if (!shapeCache.has(sk)) {
      const A = k.A === -1 ? binPolygon : shapes[sA].poly;
      shapeCache.set(sk, computeNfp(A, shapes[sB].poly, k.Arotation, k.Brotation, k.inside));
    }
    return shapeCache.get(sk);
  };
  const nfpCache = new Proxy({}, { get: (_, key) => (typeof key === 'string' && key[0] === '{' ? nfpFor(key) : undefined) });

  const adam = tree.slice(0).sort((a, b) => Math.abs(GeometryUtil.polygonArea(b)) - Math.abs(GeometryUtil.polygonArea(a)));
  const GA = new GeneticAlgorithm(adam, binPolygon, cfg);

  const t0 = Date.now();
  let best = null, gens = 0, evals = 0;
  const evaluate = (individual) => {
    const placelist = individual.placement.map((p, i) => { const c = p.map(q => ({ ...q })); c.id = p.id; c.rotation = individual.rotation[i]; return c; });
    const worker = new PlacementWorker(binPolygon, placelist, placelist.map(p => p.id), individual.rotation, cfg, nfpCache);
    globalThis.global = globalThis; globalThis.env = { self: worker };
    const res = worker.placePaths(placelist);
    evals++;
    individual.fitness = res.fitness;
    if (!best || res.fitness < best.fitness) best = res;
  };
  for (;;) {
    for (const ind of GA.population) if (!ind.fitness) evaluate(ind);
    gens++;
    const elapsed = (Date.now() - t0) / 1000;
    if (cfg.generations ? gens >= cfg.generations : elapsed >= cfg.timeLimitSec) break;
    GA.generation();
  }

  // posições → pontos (no referencial de entrada)
  const bins = best.placements.map(bin => bin.map(pl => {
    // polígono ORIGINAL (sem a simplificação do cleanPolygon) com a mesma
    // transformação — a validação de sobreposição fica rigorosa
    const r = rotatePolygon(shapes[tree[pl.id].shape].orig, pl.rotation);
    const pts = r.map(p => ({ x: p.x + pl.x, y: p.y + pl.y }));
    return { id: shapes[tree[pl.id].shape].id, rotation: pl.rotation, points: swap(pts).map(p => [p.x, p.y]) };
  }));
  const unplaced = (best.paths || []).length;
  return { bins, unplaced, fitness: best.fitness, generations: gens, evaluations: evals, seconds: (Date.now() - t0) / 1000 };
}

const chunks = [];
process.stdin.on('data', d => chunks.push(d));
process.stdin.on('end', () => {
  try {
    process.stdout.write(JSON.stringify(run(JSON.parse(Buffer.concat(chunks).toString('utf8')))));
  } catch (err) {
    process.stderr.write((err.stack || err.message) + '\n');
    process.exit(1);
  }
});
