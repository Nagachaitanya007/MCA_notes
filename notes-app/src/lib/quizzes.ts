import fs from 'fs';
import path from 'path';
import { supabase } from './supabase';

const getRootDirectory = () => {
  const cwd = process.cwd();
  
  // Local Priority
  if (fs.existsSync(path.join(cwd, 'generate_study_note.py'))) return cwd;
  const parentDir = path.join(cwd, '..');
  if (fs.existsSync(path.join(parentDir, 'generate_study_note.py'))) return parentDir;

  // Production Fallback
  const prodPath = path.join(cwd, 'public', 'data-root');
  if (fs.existsSync(prodPath)) return prodPath;

  return cwd;
};

// Check for Quiz-History inside the smart root
const quizDirectory = path.join(getRootDirectory(), 'Quiz-History');

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

export async function getAllQuizzes(): Promise<QuizData[]> {
  const allQuizzes: QuizData[] = [];

  // 1. Fetch from Supabase
  try {
    const { data: dbQuizzes, error } = await supabase
      .from('quizzes')
      .select('*')
      .order('quiz_date', { ascending: false });

    if (!error && dbQuizzes) {
      dbQuizzes.forEach((quiz) => {
        allQuizzes.push({
          date: quiz.quiz_date,
          topic: quiz.topic,
          questions: quiz.questions,
        });
      });
    }
  } catch (e) {
    console.error('Failed to fetch quizzes from Supabase:', e);
  }

  // 2. Fetch from Local Files (Fallback)
  if (fs.existsSync(quizDirectory)) {
    const files = fs.readdirSync(quizDirectory)
      .filter((f) => f.endsWith('.json'))
      .sort()
      .reverse();

    const localQuizzes = files.map((file) => {
      try {
        const filePath = path.join(quizDirectory, file);
        const contents = fs.readFileSync(filePath, 'utf8');
        const data = JSON.parse(contents);
        const dateMatch = file.match(/quiz-(\d{4}-\d{2}-\d{2})/);
        const date = dateMatch ? dateMatch[1] : file;

        return {
          date,
          topic: data.topic || 'General',
          questions: data.questions || [],
        };
      } catch (e) {
        console.error(`Error reading local quiz: ${file}`, e);
        return null;
      }
    }).filter((q): q is QuizData => q !== null);

    // Combine and remove duplicates
    localQuizzes.forEach(lq => {
      if (!allQuizzes.find(aq => aq.date === lq.date)) {
        allQuizzes.push(lq);
      }
    });
  }

  return allQuizzes.sort((a, b) => (a.date < b.date ? 1 : -1));
}
