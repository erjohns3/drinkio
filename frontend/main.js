import React from 'https://unpkg.com/react@17/umd/react.development.js';
import ReactDOM from 'https://unpkg.com/react-dom@17/umd/react-dom.development.js';
import htm from 'https://unpkg.com/htm?module'

const html = htm.bind(h);

ReactDOM.render(
    html`<h1>Hello, world!</h1>`,
    document.getElementById('root')
);

console.log("loaded 2");