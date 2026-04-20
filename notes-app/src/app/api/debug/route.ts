import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  const cwd = process.cwd();
  const parent = path.join(cwd, '..');
  const publicData = path.join(cwd, 'public', 'data-root');

  const info = {
    cwd,
    cwd_contents: fs.existsSync(cwd) ? fs.readdirSync(cwd).filter(f => !f.startsWith('.')) : 'not found',
    parent_contents: fs.existsSync(parent) ? fs.readdirSync(parent).filter(f => !f.startsWith('.')) : 'not found',
    public_data_exists: fs.existsSync(publicData),
    public_data_contents: fs.existsSync(publicData) ? fs.readdirSync(publicData).filter(f => !f.startsWith('.')) : 'not found',
  };

  return NextResponse.json(info);
}
