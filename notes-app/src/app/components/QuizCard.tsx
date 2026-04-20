'use client';

import { useState } from 'react';

interface QuizQuestion {
  id: number;
  scenario: string;
  question: string;
  options: string[];
  correct_answer_letter: string;
  correct_answer_text: string;
  explanation: string;
}

interface QuizData {
  date: string;
  topic: string;
  questions: QuizQuestion[];
}

export default function QuizCard({ quiz }: { quiz: QuizData }) {
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});

  const selectAnswer = (questionId: number, letter: string) => {
    if (revealed[questionId]) return; // Already revealed
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: letter }));
  };

  const revealAnswer = (questionId: number) => {
    setRevealed((prev) => ({ ...prev, [questionId]: true }));
  };

  return (
    <div className="bg-gray-900/50 border border-gray-800/60 rounded-xl overflow-hidden">
      {/* Quiz Header */}
      <div className="px-4 sm:px-6 py-4 border-b border-gray-800/60 flex justify-between items-center bg-gray-900/30">
        <div>
          <h3 className="text-sm sm:text-base font-semibold text-white truncate max-w-[200px] sm:max-w-none">{quiz.topic}</h3>
          <p className="text-[10px] sm:text-xs text-gray-500 mt-0.5">
            {new Date(quiz.date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
          </p>
        </div>
        <span className="text-[10px] sm:text-xs text-gray-600 font-medium">{quiz.questions.length} Qs</span>
      </div>

      {/* Questions */}
      <div className="divide-y divide-gray-800/40">
        {quiz.questions.map((q) => {
          const isRevealed = revealed[q.id];
          const userAnswer = selectedAnswers[q.id];
          const isCorrect = userAnswer === q.correct_answer_letter;

          return (
            <div key={q.id} className="px-4 sm:px-6 py-5">
              {/* Scenario */}
              <p className="text-xs sm:text-sm text-gray-500 italic mb-3 leading-relaxed">{q.scenario}</p>

              {/* Question */}
              <p className="text-sm sm:text-base font-medium text-gray-200 mb-4 leading-snug">
                {q.id}. {q.question}
              </p>

              {/* Options */}
              <div className="space-y-2 mb-4">
                {q.options.map((opt) => {
                  const letter = opt.charAt(0);
                  const isSelected = userAnswer === letter;
                  const isCorrectOption = q.correct_answer_letter === letter;

                  let optionStyle = 'bg-gray-800/30 border-gray-800/50 text-gray-400 hover:border-gray-700 cursor-pointer';
                  if (isRevealed) {
                    if (isCorrectOption) {
                      optionStyle = 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
                    } else if (isSelected && !isCorrect) {
                      optionStyle = 'bg-red-500/10 border-red-500/30 text-red-400';
                    } else {
                      optionStyle = 'bg-gray-800/20 border-gray-800/20 text-gray-600';
                    }
                  } else if (isSelected) {
                    optionStyle = 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400 shadow-sm shadow-indigo-500/10';
                  }

                  return (
                    <button
                      key={opt}
                      onClick={() => selectAnswer(q.id, letter)}
                      disabled={isRevealed}
                      className={`w-full text-left px-4 py-2.5 rounded-lg border text-xs sm:text-sm transition-all duration-200 ${optionStyle}`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>

              {/* Reveal / Result */}
              {!isRevealed ? (
                <button
                  onClick={() => revealAnswer(q.id)}
                  disabled={!userAnswer}
                  className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 disabled:text-gray-700 disabled:cursor-not-allowed transition-colors"
                >
                  {userAnswer ? 'Reveal Answer →' : 'Select an option first'}
                </button>
              ) : (
                <div className={`mt-3 p-3 rounded-lg text-xs sm:text-sm ${isCorrect ? 'bg-emerald-500/5 border border-emerald-500/20' : 'bg-red-500/5 border border-red-500/20'}`}>
                  <p className={`font-semibold mb-1 ${isCorrect ? 'text-emerald-400' : 'text-red-400'}`}>
                    {isCorrect ? '✓ Correct!' : `✗ Incorrect — Answer: ${q.correct_answer_text}`}
                  </p>
                  <p className="text-gray-400 text-[11px] sm:text-xs leading-relaxed">{q.explanation}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
