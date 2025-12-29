/**
 * Enhanced bash_docker handler that supports heredocs
 *
 * This module provides a solution for handling heredoc syntax in Docker exec commands
 * by detecting heredocs and converting them to a more compatible format.
 */

export function transformHeredocCommand(command: string): string {
  // Pattern to detect heredoc: cat > file << 'EOF' or cat > file <<EOF
  const heredocPattern = /cat\s*>\s*([^\s]+)\s*<<\s*['"]?(\w+)['"]?\n([\s\S]*?)\n\2/;

  const match = command.match(heredocPattern);

  if (!match) {
    // No heredoc detected, return original command
    return command;
  }

  const [fullMatch, fileName, delimiter, content] = match;

  // Convert heredoc to printf command with proper escaping
  // This preserves newlines and special characters
  const escapedContent = content
    .replace(/\\/g, '\\\\')  // Escape backslashes first
    .replace(/"/g, '\\"')    // Escape quotes
    .replace(/\$/g, '\\$')   // Escape dollar signs
    .replace(/`/g, '\\`')    // Escape backticks
    .split('\n')
    .map(line => line + '\\n')
    .join('');

  // Remove trailing \n
  const finalContent = escapedContent.slice(0, -2);

  // Build printf command
  const printfCommand = `printf "${finalContent}" > ${fileName}`;

  // Replace heredoc with printf in original command
  return command.replace(fullMatch, printfCommand);
}

/**
 * Alternative: Use base64 encoding for complex content
 * This is more reliable for binary data or complex scripts
 */
export function transformHeredocCommandBase64(command: string): string {
  const heredocPattern = /cat\s*>\s*([^\s]+)\s*<<\s*['"]?(\w+)['"]?\n([\s\S]*?)\n\2/;

  const match = command.match(heredocPattern);

  if (!match) {
    return command;
  }

  const [fullMatch, fileName, delimiter, content] = match;

  // Convert content to base64
  const base64Content = Buffer.from(content).toString('base64');

  // Build command using base64 decoding
  const base64Command = `echo "${base64Content}" | base64 -d > ${fileName}`;

  return command.replace(fullMatch, base64Command);
}

/**
 * Another approach: Create a temporary script file
 * This is useful for very long heredocs
 */
export async function handleHeredocViaScript(
  containerName: string,
  command: string,
  execAsync: Function
): Promise<{ stdout: string; stderr: string }> {
  const heredocPattern = /cat\s*>\s*([^\s]+)\s*<<\s*['"]?(\w+)['"]?\n([\s\S]*?)\n\2/;
  const match = command.match(heredocPattern);

  if (!match) {
    // No heredoc, execute normally
    const dockerCommand = `docker exec ${containerName} /bin/bash -c ${JSON.stringify(command)}`;
    return execAsync(dockerCommand);
  }

  const [fullMatch, fileName, delimiter, content] = match;

  // Create a unique script name
  const scriptName = `/tmp/heredoc_${Date.now()}.sh`;

  // Create the script content
  const scriptContent = `#!/bin/bash
cat > ${fileName} << '${delimiter}'
${content}
${delimiter}
`;

  // First, create the script file
  const createScriptCmd = `docker exec ${containerName} /bin/bash -c ${JSON.stringify(`echo ${JSON.stringify(scriptContent)} > ${scriptName} && chmod +x ${scriptName}`)}`;
  await execAsync(createScriptCmd);

  // Execute the script
  const executeScriptCmd = `docker exec ${containerName} ${scriptName}`;
  const result = await execAsync(executeScriptCmd);

  // Clean up the script
  const cleanupCmd = `docker exec ${containerName} rm ${scriptName}`;
  await execAsync(cleanupCmd).catch(() => {}); // Ignore cleanup errors

  // If there were more commands after the heredoc, execute them
  const remainingCommand = command.replace(fullMatch, '').trim();
  if (remainingCommand) {
    const remainingCmd = `docker exec ${containerName} /bin/bash -c ${JSON.stringify(remainingCommand)}`;
    const remainingResult = await execAsync(remainingCmd);
    return {
      stdout: result.stdout + remainingResult.stdout,
      stderr: result.stderr + remainingResult.stderr
    };
  }

  return result;
}

// Export all strategies
export default {
  transformHeredocCommand,
  transformHeredocCommandBase64,
  handleHeredocViaScript
};