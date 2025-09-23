// web-test-runner.config.mjs

export default {
  // Define which files to run tests for.
  // This glob pattern finds all files in 'src' ending with .test.js.
  files: 'src/**/*.test.js',

  // Run tests in a real browser environment.
  // You may need to install a browser launcher, e.g., for Chrome:
  // npm install @web/test-runner-playwright --save-dev
  // Then you can configure it to use specific browsers.
  // For now, it will use the default browser discovery.
  
  // Use a Node.js build of your project.
  nodeResolve: true,
};