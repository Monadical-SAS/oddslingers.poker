const path = require('path');

module.exports = {
  mode: 'production',
  target: 'web',
  resolve: {
    fallback: {
      path: false,
      fs: false,
    },
  },
  entry: {
    'user': './pages/user.js',
    'table': './pages/table.js',
    'tables': './pages/tables.js',
    'leaderboard': './pages/leaderboard.js',
    'sidebet': './pages/sidebet.js',
    'tournament-summary': './pages/tournament-summary.js',
    'debugger': './pages/debugger.js',
  },
  output: {
    path: path.resolve(__dirname, 'build/pages'),
    filename: '[name].js',
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader"
        }
      }
    ]
  },
  optimization: {
    minimize: true,
  },
  performance: {
    maxEntrypointSize: 700000,
  }
};

