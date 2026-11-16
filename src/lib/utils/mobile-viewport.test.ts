import { describe, it, expect } from 'vitest';
import { viewportGeometry } from './mobile-viewport';

describe('visible mobile viewport', () => {
	it('uses the measured visible height when only the visual viewport shrinks', () => {
		expect(viewportGeometry(844, 340, 100, 1)).toEqual({ height: 340, top: 100 });
	});
	it('does not subtract the keyboard twice when the layout viewport already shrank', () => {
		expect(viewportGeometry(340, 340, 0, 1)).toEqual({ height: 340, top: 0 });
		expect(viewportGeometry(340, 844, 0, 1)).toEqual({ height: 340, top: 0 });
	});
	it('leaves pinch zoom alone and ignores unavailable measurements', () => {
		expect(viewportGeometry(844, 422, 100, 2)).toBeNull();
		expect(viewportGeometry(844, 0, 0, 1)).toBeNull();
	});
});
