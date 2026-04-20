import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

// Ultra-robust root detector
const getNotesDirectory = () => {
  const cwd = process.cwd();
  
  // 1. Local Priority: Check if we are inside notes-app or at the repo root
  // We look for 'generate_study_note.py' as a marker of the real root
  if (fs.existsSync(path.join(cwd, 'generate_study_note.py'))) return cwd;
  
  const parentDir = path.join(cwd, '..');
  if (fs.existsSync(path.join(parentDir, 'generate_study_note.py'))) return parentDir;

  // 2. Production Fallback: Check for the folder created during Render build
  const prodPath = path.join(cwd, 'public', 'data-root');
  if (fs.existsSync(prodPath)) return prodPath;

  // 3. Ultimate fallback
  return cwd;
};

const notesDirectory = getNotesDirectory();

export interface NoteData {
  id: string;
  title: string;
  date: string;
  folder: string;
  readingTime: number;
  wordCount: number;
  headings: { text: string; level: number; slug: string }[];
  contentMarkdown?: string;
}

function calculateReadingTime(content: string): { readingTime: number; wordCount: number } {
  const plainText = content
    .replace(/```[\s\S]*?```/g, '')
    .replace(/[#*_~`>\-|]/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  const words = plainText.split(/\s+/).filter((w) => w.length > 0);
  const wordCount = words.length;
  const readingTime = Math.max(1, Math.ceil(wordCount / 200));
  return { readingTime, wordCount };
}

function extractHeadings(content: string): { text: string; level: number; slug: string }[] {
  const headingRegex = /^(#{2,4})\s+(.+)$/gm;
  const headings: { text: string; level: number; slug: string }[] = [];
  let match;
  while ((match = headingRegex.exec(content)) !== null) {
    const text = match[2].replace(/[*_`]/g, '').trim();
    const slug = text
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-');
    headings.push({ text, level: match[1].length, slug });
  }
  return headings;
}

// Recursively find all markdown files
function getAllMarkdownFiles(dirPath: string, arrayOfFiles: string[] = []) {
  try {
    if (!fs.existsSync(dirPath)) return arrayOfFiles;
    const files = fs.readdirSync(dirPath);

    files.forEach((file) => {
      // Ignore app internals and system folders
      if (['notes-app', '.git', 'node_modules', 'scratch', '.github', '.next'].includes(file)) {
        return;
      }

      try {
        const absolutePath = path.join(dirPath, file);
        const stat = fs.statSync(absolutePath);

        if (stat.isDirectory()) {
          arrayOfFiles = getAllMarkdownFiles(absolutePath, arrayOfFiles);
        } else if (file.endsWith('.md') && !['README.md', 'task.md', 'implementation_plan.md'].includes(file)) {
          arrayOfFiles.push(absolutePath);
        }
      } catch (e) {
        // Skip individual files/folders that cause errors
        console.error(`Error scanning ${file}:`, e);
      }
    });
  } catch (e) {
    console.error(`Error reading directory ${dirPath}:`, e);
  }

  return arrayOfFiles;
}

export function getSortedNotesData(): NoteData[] {
  const filePaths = getAllMarkdownFiles(notesDirectory);

  const allNotesData = filePaths.map((filePath) => {
    try {
      const fileContents = fs.readFileSync(filePath, 'utf8');
      const matterResult = matter(fileContents);
      const relativePath = path.relative(notesDirectory, filePath);
      const id = relativePath.replace(/\.md$/, '').replace(/\\/g, '/');
      const folder = path.dirname(relativePath).replace(/\\/g, '/');

      // Use frontmatter if available, otherwise fallback to filename/disk info
      const title = matterResult.data.title || path.basename(filePath, '.md').replace(/-/g, ' ');
      const date = matterResult.data.date || fs.statSync(filePath).mtime.toISOString();
      
      const { readingTime, wordCount } = calculateReadingTime(fileContents);

      return {
        id,
        title,
        date: typeof date === 'string' ? date : date.toISOString(),
        folder: folder === '.' ? 'Root' : folder,
        readingTime,
        wordCount,
        headings: extractHeadings(fileContents),
      };
    } catch (error) {
      console.error(`Error parsing note: ${filePath}`, error);
      return null;
    }
  }).filter((note): note is NoteData => note !== null);

  return allNotesData.sort((a, b) => {
    if (a.date < b.date) return 1;
    return -1;
  });
}

export function getNoteData(id: string): NoteData {
  const fullPath = path.join(notesDirectory, `${id}.md`);
  const fileContents = fs.readFileSync(fullPath, 'utf8');
  const matterResult = matter(fileContents);

  let title = matterResult.data.title;
  if (!title) {
    const h1Match = fileContents.match(/^#\s+(.*)/m);
    title = h1Match ? h1Match[1] : path.basename(fullPath, '.md');
  }

  let date = matterResult.data.date;
  if (!date) {
    date = fs.statSync(fullPath).birthtime.toISOString();
  }

  const folder = path.dirname(id).replace(/\\/g, '/');
  const { readingTime, wordCount } = calculateReadingTime(matterResult.content);
  const headings = extractHeadings(matterResult.content);

  return {
    id,
    title,
    date,
    folder,
    readingTime,
    wordCount,
    headings,
    contentMarkdown: matterResult.content,
  };
}
