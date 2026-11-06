// DioItem — one item of the shared MOTION LIBRARY drawn live (Oct 29 2026). Used by the Explainer "dio" pictures (kit.tsx
// Visual), MIR EXPLAINED's Drawing figures ("lib:<id>", figures.tsx) and anything else that wants a library character / animal /
// object / place that MOVES. Same engine as the Diorama (diorama_engine.ts drawLibItem), so every editor shares one look.
import React, {useLayoutEffect, useRef} from 'react';
import {drawLibItem} from './diorama_engine';
import CHARS from './lib_chars.json';

/* "char:doctor" · "act:drive" · "ride:bike" · "animal:dog" · "animal:dog:run" · "obj:cup" · "prop:tent" · "place:apartment" →
   the engine item. A place kit (or any item the server already resolved) can be passed whole as `item`. */
export const libItem = (id?: string, item?: any): any => {
	if (item && item.type) return item;
	const [cat, key, act] = String(id || '').replace(/^lib:/, '').split(':');
	if (cat === 'char') {const c = (CHARS as any)[key]; return c ? {type: 'char', look: c.look, act: act || c.act} : {type: 'char', act: 'stand'};}
	if (cat === 'act' || cat === 'ride') return {type: 'act', act: key};
	if (cat === 'animal') return {type: 'animal', kind: key, act: act || 'idle'};
	if (cat === 'obj') return {type: 'obj', name: key};
	if (cat === 'prop') return {type: 'prop', id: key};
	if (cat === 'vfx') return {type: 'vfx', kind: key};
	if (cat === 'place') return {type: 'place', id: key};
	return null;
};
export const isLib = (id?: string) => /^(lib:)?(char|act|ride|animal|obj|prop|place|vfx):/.test(String(id || ''));

export const DioItem: React.FC<{id?: string; item?: any; size: number; t: number; bg?: boolean; style?: React.CSSProperties}> = ({id, item, size, t, bg = false, style}) => {
	const ref = useRef<HTMLCanvasElement>(null);
	const it = libItem(id, item);
	const px = Math.max(16, Math.round(size * 2)) & ~1;          // 2x for crisp edges when the picture is scaled
	useLayoutEffect(() => {const c = ref.current && ref.current.getContext('2d'); if (!c || !it) return; c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, px, px);
		try {drawLibItem(c, px, px, t, it, {bg});} catch (e) {/* a bad id must never abort a render */}}, [t, px, JSON.stringify(it), bg]);
	if (!it) return null;
	return <canvas ref={ref} width={px} height={px} style={{width: size, height: size, display: 'block', ...style}} />;
};
