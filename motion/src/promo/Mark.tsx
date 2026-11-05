// Transparent flask mark (256×256) — MML's render watermark.
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {FlaskLogo} from './LogoOpen';

export const FlaskMark: React.FC = () => (
	<AbsoluteFill style={{background: 'transparent', padding: 18}}>
		<FlaskLogo draw={1} ring={1} bubbles={1} glow={0.15} spin={0.02} />
	</AbsoluteFill>
);
