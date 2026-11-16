const net = require('net');
const { LanguageClient, State, ErrorAction, CloseAction } = require('vscode-languageclient/node');
const vscode = require('vscode');



function getWorkspaceRoot() {
  const roots = vscode.workspace.workspaceFolders ?? [];
  if (roots.length !== 1) {
    return null;
  }

  const [root] = roots;
  return root;
}


let client = null;


async function ensureDown() {
  if (client?.state == State.Running) {
    await client.stop();
  }
  client = null;
}


async function restart() {
  await ensureDown();
  
  const wsRoot = getWorkspaceRoot();

  if (!wsRoot) {
    // client.outputChannel.appendLine("Not a workspace with a single root => not activating the Dyrel LSP client");
    return;
  }

  const serverOptions = () => {
    return new Promise((resolve, reject) => {
      const socket = net.connect({ host: '127.0.0.1', port: 17017 });
      socket.once('connect', () => {
        // client.outputChannel.appendLine(`Connected to 17017`);
        resolve({ reader: socket, writer: socket });
      });
      socket.once('error', function (e) {
        // client?.outputChannel.appendLine(`Connection to 17017 failed: ${e}`);
        reject(e);
      });
    });
  };

  const clientOptions = {
    documentSelector: [
      {
        scheme: 'file',
        language: 'python',
        pattern: `${wsRoot.uri.fsPath}/sample/*.py`
      },
    ],
    errorHandler: {
      error: { action: ErrorAction.Shutdown },
      closed: {action: CloseAction.DoNotRestart, handled: true }
    }
  };

  client = new LanguageClient('Dyrel LSP', 'Dyrel LSP client', serverOptions, clientOptions);

  await client.start();
}


exports.activate = async (context) => {
  context.subscriptions.push(vscode.commands.registerCommand('dyrel.restart', restart));

  await restart();
};

exports.deactivate = ensureDown;
