import { render } from 'solid-js/web';
import { App } from './app';
import './index.css';

const root = document.getElementById('app');
if (root) render(() => <App />, root);
