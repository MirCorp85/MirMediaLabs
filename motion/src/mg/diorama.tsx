// DIORAMA scene — the whole narrated story as ONE continuous canvas shot (engine: diorama_engine.ts).
import React, {useLayoutEffect, useRef, useState, useEffect} from 'react';
import {continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {drawDiorama, preloadMint, setSpriteResolver} from './diorama_engine';
import {mgFontsReady} from './kit';

export const Diorama: React.FC<any> = ({p, proj}) => {
	const f = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const ref = useRef<HTMLCanvasElement>(null);
	const [ready, setReady] = useState(false);
	const [h] = useState(() => delayRender('diorama fonts', {timeoutInMilliseconds: 20000}));
	useEffect(() => {setSpriteResolver((u) => (/^(data:|https?:|file:)/.test(u) ? u : staticFile(u)));      // minted image sprites load before the first frame
		Promise.all([mgFontsReady((proj && proj.fontBase) || 'fonts/'), preloadMint(p.mint)]).then(() => {setReady(true); continueRender(h);});}, [h, proj, p.mint]);
	useLayoutEffect(() => {const c = ref.current && ref.current.getContext('2d'); if (c) drawDiorama(c, width, height, f / fps + (+p.offset || 0), p);}, [f, fps, width, height, p, ready]);
	return <canvas ref={ref} width={width} height={height} style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />;
};
