#!/usr/bin/env node
/**
 * MCP Server for Task Management
 * Provides structured task management capabilities for YokeFlow agents
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema
} from '@modelcontextprotocol/sdk/types.js';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { exec } from 'child_process';
import { promisify } from 'util';
// Import database implementation
import { TaskDatabase } from './database.js';
import type { NewTask, NewTest, NewEpic } from './types.js';

const execAsync = promisify(exec);

// Initialize database
const db = new TaskDatabase();

// Log database info
console.error(`Using PostgreSQL database for project: ${process.env.PROJECT_ID || 'unknown'}`);

// Helper to define ID field that works with both legacy (number) and PostgreSQL (string/UUID)
const idFieldSchema = {
  oneOf: [
    { type: 'number' },
    { type: 'string' }
  ]
};

// Define tool schemas
const tools: Tool[] = [
  {
    name: 'task_status',
    description: 'Get overall project status including epics, tasks, and tests progress',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  },
  {
    name: 'get_next_task',
    description: 'Get the next highest priority incomplete task to work on',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  },
  {
    name: 'list_epics',
    description: 'List all epics or epics that need task expansion',
    inputSchema: {
      type: 'object',
      properties: {
        needs_expansion: {
          type: 'boolean',
          description: 'If true, only show epics with no tasks'
        }
      }
    }
  },
  {
    name: 'get_epic',
    description: 'Get details of a specific epic including its tasks',
    inputSchema: {
      type: 'object',
      properties: {
        epic_id: {
          ...idFieldSchema,
          description: 'The ID of the epic'
        }
      },
      required: ['epic_id']
    }
  },
  {
    name: 'list_tasks',
    description: 'List tasks with optional filtering',
    inputSchema: {
      type: 'object',
      properties: {
        epic_id: {
          ...idFieldSchema,
          description: 'Filter by epic ID'
        },
        only_pending: {
          type: 'boolean',
          description: 'Only show incomplete tasks'
        }
      }
    }
  },
  {
    name: 'get_task',
    description: 'Get detailed information about a specific task including its tests',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          ...idFieldSchema,
          description: 'The ID of the task'
        }
      },
      required: ['task_id']
    }
  },
  {
    name: 'list_tests',
    description: 'List all tests for a specific task',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          ...idFieldSchema,
          description: 'The ID of the task'
        }
      },
      required: ['task_id']
    }
  },
  {
    name: 'create_epic',
    description: 'Create a new epic',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Name of the epic'
        },
        description: {
          type: 'string',
          description: 'Detailed description of the epic'
        },
        priority: {
          type: 'number',
          description: 'Priority (lower number = higher priority)'
        }
      },
      required: ['name', 'priority']
    }
  },
  {
    name: 'create_task',
    description: 'Create a new task within an epic',
    inputSchema: {
      type: 'object',
      properties: {
        epic_id: {
          ...idFieldSchema,
          description: 'The epic this task belongs to'
        },
        description: {
          type: 'string',
          description: 'Brief description of the task'
        },
        action: {
          type: 'string',
          description: 'Detailed implementation instructions'
        },
        priority: {
          type: 'number',
          description: 'Priority within the epic (optional, auto-increments)'
        }
      },
      required: ['epic_id', 'description', 'action']
    }
  },
  {
    name: 'create_test',
    description: 'Create a test case for a task',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          ...idFieldSchema,
          description: 'The task this test belongs to'
        },
        category: {
          type: 'string',
          enum: ['functional', 'style', 'accessibility', 'performance'],
          description: 'Category of test'
        },
        description: {
          type: 'string',
          description: 'What this test verifies'
        },
        steps: {
          type: 'array',
          items: { type: 'string' },
          description: 'Array of test steps to perform'
        }
      },
      required: ['task_id', 'category', 'description', 'steps']
    }
  },
  {
    name: 'update_task_status',
    description: 'Mark a task as done or not done',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          ...idFieldSchema,
          description: 'The ID of the task'
        },
        done: {
          type: 'boolean',
          description: 'Whether the task is completed'
        }
      },
      required: ['task_id', 'done']
    }
  },
  {
    name: 'start_task',
    description: 'Mark a task as started/in progress',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          ...idFieldSchema,
          description: 'The ID of the task to start'
        }
      },
      required: ['task_id']
    }
  },
  {
    name: 'update_test_result',
    description: 'Mark a test as passing or failing',
    inputSchema: {
      type: 'object',
      properties: {
        test_id: {
          ...idFieldSchema,
          description: 'The ID of the test'
        },
        passes: {
          type: 'boolean',
          description: 'Whether the test passes'
        }
      },
      required: ['test_id', 'passes']
    }
  },
  {
    name: 'expand_epic',
    description: 'Break down an epic into multiple tasks',
    inputSchema: {
      type: 'object',
      properties: {
        epic_id: {
          ...idFieldSchema,
          description: 'The ID of the epic to expand'
        },
        tasks: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              action: { type: 'string' },
              priority: { type: 'number' }
            },
            required: ['description', 'action']
          },
          description: 'Array of tasks to create for this epic'
        }
      },
      required: ['epic_id', 'tasks']
    }
  },
  // DEPRECATED: log_session tool removed - sessions are now managed by orchestrator
  // It was creating phantom sessions with status='completed' but no timestamps
  {
    name: 'mark_project_complete',
    description: 'Mark the project as complete when all epics, tasks, and tests are finished. Sets the completion timestamp in the database.',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  },
  {
    name: 'get_session_history',
    description: 'Get recent session history',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of sessions to return (default: 10)'
        }
      }
    }
  },
  {
    name: 'bash_docker',
    description: 'Execute a bash command in the Docker sandbox. Use this instead of the regular Bash tool when a sandbox is active. Returns stdout, stderr, and exit code.',
    inputSchema: {
      type: 'object',
      properties: {
        command: {
          type: 'string',
          description: 'The bash command to execute in the Docker container'
        },
        description: {
          type: 'string',
          description: 'Brief description of what this command does (for logging)'
        }
      },
      required: ['command']
    }
  }
];

// Create MCP server
const server = new Server(
  {
    name: 'mcp-task-manager',
    version: '1.0.0'
  },
  {
    capabilities: {
      tools: {},
      resources: {}
    }
  }
);

// Handle tool listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools };
});

// Handle resource listing (we don't use resources, but SDK might expect this)
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return { resources: [] };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'task_status':
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(await db.getProjectStatus(), null, 2)
            }
          ]
        };

      case 'get_next_task':
        const nextTask = await db.getNextTask();
        if (!nextTask) {
          return {
            content: [
              {
                type: 'text',
                text: 'No pending tasks found. Consider expanding epics that need tasks.'
              }
            ]
          };
        }
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(nextTask, null, 2)
            }
          ]
        };

      case 'list_epics':
        const epics = await db.listEpics(args?.needs_expansion as boolean);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(epics, null, 2)
            }
          ]
        };

      case 'get_epic':
        const epic = await db.getEpic(args?.epic_id as any);
        if (!epic) {
          throw new Error(`Epic ${args?.epic_id} not found`);
        }
        const epicProgress = await db.getEpicProgress(args?.epic_id as any);
        const epicTasks = await db.listTasks(args?.epic_id as any);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({ epic, progress: epicProgress[0], tasks: epicTasks }, null, 2)
            }
          ]
        };

      case 'list_tasks':
        const tasks = await db.listTasks(
          args?.epic_id as any | undefined,
          args?.only_pending as boolean
        );
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(tasks, null, 2)
            }
          ]
        };

      case 'get_task':
        const task = await db.getTask(args?.task_id as any);
        if (!task) {
          throw new Error(`Task ${args?.task_id} not found`);
        }
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(task, null, 2)
            }
          ]
        };

      case 'list_tests':
        const tests = await db.listTests(args?.task_id as any);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(tests, null, 2)
            }
          ]
        };

      case 'create_epic':
        const newEpic: NewEpic = {
          name: args?.name as string,
          description: args?.description as string,
          priority: args?.priority as number
        };
        const createdEpic = await db.createEpic(newEpic);
        return {
          content: [
            {
              type: 'text',
              text: `Created epic ${createdEpic.id}: ${createdEpic.name}`
            }
          ]
        };

      case 'create_task':
        const newTask: NewTask = {
          epic_id: args?.epic_id as any,
          description: args?.description as string,
          action: args?.action as string,
          priority: args?.priority as number
        };
        const createdTask = await db.createTask(newTask);
        return {
          content: [
            {
              type: 'text',
              text: `Created task ${createdTask.id}: ${createdTask.description}`
            }
          ]
        };

      case 'create_test':
        const newTest: NewTest = {
          task_id: args?.task_id as any,
          category: args?.category as any,
          description: args?.description as string,
          steps: args?.steps as string[]
        };
        const createdTest = await db.createTest(newTest);
        return {
          content: [
            {
              type: 'text',
              text: `Created test ${createdTest.id}: ${createdTest.description}`
            }
          ]
        };

      case 'update_task_status':
        const updatedTask = await db.updateTaskStatus(
          args?.task_id as any,
          args?.done as boolean
        );
        if (!updatedTask) {
          throw new Error(`Task ${args?.task_id} not found`);
        }
        return {
          content: [
            {
              type: 'text',
              text: `Task ${updatedTask.id} marked as ${args?.done ? 'completed' : 'incomplete'}`
            }
          ]
        };

      case 'start_task':
        await db.startTask(args?.task_id as any);
        return {
          content: [
            {
              type: 'text',
              text: `Task ${args?.task_id} marked as started`
            }
          ]
        };

      case 'update_test_result':
        const updatedTest = await db.updateTestResult(
          args?.test_id as any,
          args?.passes as boolean
        );
        if (!updatedTest) {
          throw new Error(`Test ${args?.test_id} not found`);
        }
        return {
          content: [
            {
              type: 'text',
              text: `Test ${updatedTest.id} marked as ${args?.passes ? 'passing' : 'failing'}`
            }
          ]
        };

      case 'expand_epic':
        const expandedTasks = await db.expandEpic(
          args?.epic_id as any,
          args?.tasks as NewTask[]
        );
        return {
          content: [
            {
              type: 'text',
              text: `Expanded epic ${args?.epic_id} with ${expandedTasks.length} tasks:\n${
                expandedTasks.map(t => `- Task ${t.id}: ${t.description}`).join('\n')
              }`
            }
          ]
        };

      // REMOVED: case 'log_session' - deprecated tool that created phantom sessions
      // Sessions are now managed entirely by the orchestrator

      case 'mark_project_complete':
        await db.markProjectComplete();
        return {
          content: [
            {
              type: 'text',
              text: 'Project marked as complete! 🎉'
            }
          ]
        };

      case 'get_session_history':
        const sessions = await db.getSessionHistory(args?.limit as number);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(sessions, null, 2)
            }
          ]
        };

      case 'bash_docker':
        // Get Docker configuration from environment
        const containerName = process.env.DOCKER_CONTAINER_NAME || 'yokeflow-container';
        let command = args?.command as string;

        if (!command) {
          throw new Error('Command is required for bash_docker');
        }

        console.error(`[bash_docker] Executing in container ${containerName}: ${command.substring(0, 100)}`);

        // Check if command contains a heredoc and transform it if needed
        const heredocPattern = /cat\s*>\s*([^\s]+)\s*<<\s*['"]?(\w+)['"]?/;
        const hasHeredoc = heredocPattern.test(command);

        if (hasHeredoc) {
          console.error(`[bash_docker] Detected heredoc syntax, transforming command`);

          // Transform heredoc to use printf or echo with base64
          const fullHeredocPattern = /cat\s*>\s*([^\s]+)\s*<<\s*['"]?(\w+)['"]?\n([\s\S]*?)\n\2/;
          const match = command.match(fullHeredocPattern);

          if (match) {
            const [fullMatch, fileName, , content] = match; // delimiter not needed for base64 approach

            // Use base64 encoding for reliability
            const base64Content = Buffer.from(content).toString('base64');
            const base64Command = `echo "${base64Content}" | base64 -d > ${fileName}`;

            // Replace heredoc with base64 command
            command = command.replace(fullMatch, base64Command);
            console.error(`[bash_docker] Transformed heredoc to base64 encoding`);
          }
        }

        try {
          // Execute command in Docker container
          const dockerCommand = `docker exec ${containerName} /bin/bash -c ${JSON.stringify(command)}`;
          const { stdout, stderr } = await execAsync(dockerCommand, {
            maxBuffer: 10 * 1024 * 1024, // 10MB buffer
            timeout: 300000 // 5 minute timeout
          });

          console.error(`[bash_docker] Command executed successfully`);

          // Return result in a format similar to regular Bash tool
          let output = stdout;
          if (stderr) {
            output += stderr;
          }

          return {
            content: [
              {
                type: 'text',
                text: output
              }
            ]
          };
        } catch (error: any) {
          // Docker exec failed - check if it's an expected exit code
          console.error(`[bash_docker] Command failed: ${error.message}`);

          // Exit code 143 = 128 + 15 (SIGTERM) - this is EXPECTED when killing processes
          // Don't treat it as an error, just return the output
          const exitCode = error.code;
          if (exitCode === 143) {
            console.error(`[bash_docker] Process terminated with SIGTERM (expected for pkill)`);
            let output = '';
            if (error.stdout) output += error.stdout;
            if (error.stderr) output += error.stderr;
            if (!output) output = 'Process terminated (SIGTERM)';

            return {
              content: [
                {
                  type: 'text',
                  text: output
                }
              ]
              // NOT marking as error for exit code 143
            };
          }

          // For other exit codes, return as error
          let errorOutput = '';
          if (error.stdout) errorOutput += error.stdout;
          if (error.stderr) errorOutput += error.stderr;
          if (!errorOutput) errorOutput = error.message;

          return {
            content: [
              {
                type: 'text',
                text: errorOutput
              }
            ],
            isError: true
          };
        }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${errorMessage}`
        }
      ],
      isError: true
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('MCP Task Manager Server started');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});

// Handle cleanup
process.on('SIGINT', () => {
  db.close();
  process.exit(0);
});

process.on('SIGTERM', () => {
  db.close();
  process.exit(0);
});