const net = require('net');
const { LanguageClient } = require('vscode-languageclient/node');
const vscode = require('vscode');


let client;

exports.activate = (context) => {
  // Connect to the already-running server; VS Code launches nothing
  const serverOptions = () =>
    new Promise((resolve, reject) => {
      const socket = net.connect({ host: '127.0.0.1', port: 17017 }, () =>
        resolve({ reader: socket, writer: socket })
      );
      socket.on('error', reject);
    });

  const clientOptions = {
    documentSelector: [
      { scheme: 'file', language: 'python', pattern: '**/sample/*.py' },
    ],
  };

  client = new LanguageClient('Dyrel LSP', 'Dyrel LSP client', serverOptions, clientOptions);
  client.start();

  context.subscriptions.push(
    vscode.commands.registerCommand('dyrel.restart', () => client.restart())
  );
};

exports.deactivate = () => client?.stop();