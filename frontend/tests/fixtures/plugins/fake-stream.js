/** Test fixture stream plugin (ES module). */
export default {
  id: 'test-fake-stream',
  name: 'Fake Stream',
  kind: 'stream',
  description: 'Fixture for loader tests',
  configSchema: {},
  start({ onStatus }) {
    onStatus?.({ state: 'open' });
    return () => onStatus?.({ state: 'closed' });
  },
};
