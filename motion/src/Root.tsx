import React from 'react';
import {Composition, Still} from 'remotion';
import {MotionProject} from './Project';
import {Project, projectDuration} from './lib';
import {EPISODES, ExplainedEpisode, ExplainedShortGeneric, shortTotal} from './explained/Episode';
import {ExplainedThumb} from './explained/Thumb';

const DEMO: Project = {
	w: 1280,
	h: 720,
	fps: 30,
	tracks: [
		{kind: 'scene', clips: [{id: 'a', type: 'title', start: 0, dur: 4, props: {text: 'MIR MOTION', sub: 'MIR MEDIA LABS', anim: 'word-pop'}}]},
	],
};

export const Root: React.FC = () => (
	<>
	{/* EXPLAINED producer comps — rendered with --props='{"ep": <resolved episode json>, ...}' (server/explainer_back.py) */}
	<Composition id="ExplainedEpisode" component={ExplainedEpisode as any} defaultProps={{ep: EPISODES.roadster}} fps={30} width={1920} height={1080} durationInFrames={300}
		calculateMetadata={({props}: any) => ({durationInFrames: Math.max(30, Math.ceil((props.ep?.total || 10) * 30))})} />
	<Composition id="ExplainedShort" component={ExplainedShortGeneric as any} defaultProps={{ep: EPISODES.roadster, cut: {ids: ['b02', 'b19'], hook: 'Preview'}}} fps={30} width={1080} height={1920} durationInFrames={300}
		calculateMetadata={({props}: any) => ({durationInFrames: Math.max(30, Math.ceil(shortTotal(props.ep, props.cut) * 30))})} />
	<Still id="ExplainedThumb" component={ExplainedThumb as any} width={1280} height={720} defaultProps={{base: 'episodes/roadster/', plate: 'st_flip.png', number: '0.81', unit: 's', hook: 'Rocket thrusters', tag: 'TESLA ROADSTER · EXPLAINED'}} />
	<Composition
		id="Project"
		component={MotionProject as any}
		defaultProps={{project: DEMO}}
		durationInFrames={120}
		fps={30}
		width={1280}
		height={720}
		calculateMetadata={({props}: any) => {
			const p: Project = props.project;
			const fps = Math.max(1, Math.min(60, +p.fps || 30));
			return {fps, width: (+p.w || 1280) & ~1, height: (+p.h || 720) & ~1, durationInFrames: Math.max(1, Math.round(projectDuration(p) * fps))};
		}}
	/>

	</>
);
