import fs from 'fs';
import path from 'path';

// Auto-detect the quiz directory
const getQuizDirectory = () => {
  const localPath = path.join(process.cwd(), '..', 'Quiz-History');
  const prodPath = path.join(process.cwd(), 'public', 'data-quizzes');
  
  if (fs.existsSync(prodPath)) return prodPath;
  return localPath;
};

const quizDirectory = getQuizDirectory();

export interface QuizQuestion {
  id: number;
  scenario: string;
  question: string;
  options: string[];
  correct_answer_letter: string;
  correct_answer_text: string;
  explanation: string;
}

export interface QuizData {
  date: string; // extracted from filename
  topic: string;
  questions: QuizQuestion[];
}

export function getAllQuizzes(): QuizData[] {
  if (!fs.existsSync(quizDirectory)) {
    return [];
  }

  const files = fs.readdirSync(quizDirectory)
    .filter((f) => f.endsWith('.json'))
    .sort()
    .reverse(); // newest first

  return files.map((file) => {
    try {
      const filePath = path.join(quizDirectory, file);
      const contents = fs.readFileSync(filePath, 'utf8');
      const data = JSON.parse(contents);
      
      // Extract date from filename like "quiz-2026-04-20.json"
      const dateMatch = file.match(/quiz-(\d{4}-\d{2}-\d{2})/);
      const date = dateMatch ? dateMatch[1] : file;

      return {
        date,
        topic: data.topic || 'General',
        questions: data.questions || [],
      };
    } catch (e) {
      console.error(`Error reading quiz: ${file}`, e);
      return null;
    }
  }).filter((q): q is QuizData => q !== null);
}
