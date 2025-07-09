-- Questions pool table
CREATE TABLE questions (
  id               SERIAL PRIMARY KEY,
  text             TEXT NOT NULL,
  cooldown_min     INT DEFAULT 720,
  last_asked_at    TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations table
CREATE TABLE conversations (
  id               SERIAL PRIMARY KEY,
  run_uuid         UUID NOT NULL,
  question_id      INT NOT NULL REFERENCES questions(id),
  started_at       TIMESTAMPTZ DEFAULT NOW(),
  finished_at      TIMESTAMPTZ
);

-- Messages table
CREATE TABLE messages (
  id              SERIAL PRIMARY KEY,
  conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT CHECK (role IN ('user','assistant','system')),
  content_md      TEXT,
  scraped_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Web searches table
CREATE TABLE web_searches (
  id              SERIAL PRIMARY KEY,
  conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
  url             TEXT,
  title           TEXT,
  fetched_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Artifacts table for screenshots and HTML dumps
CREATE TABLE artifacts (
  id              SERIAL PRIMARY KEY,
  conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
  type            TEXT CHECK (type IN ('screenshot','html','har')),
  path            TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_conversations_run_uuid ON conversations(run_uuid);
CREATE INDEX idx_conversations_started_at ON conversations(started_at);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_web_searches_conversation_id ON web_searches(conversation_id);
CREATE INDEX idx_artifacts_conversation_id ON artifacts(conversation_id);
CREATE INDEX idx_questions_last_asked_at ON questions(last_asked_at);

-- Insert sample questions
INSERT INTO questions (text, cooldown_min) VALUES
  ('Explain Bellman-Ford vs Dijkstra in one tweet', 1440),
  ('Write a bash one-liner to find duplicate files', 720),
  ('What are the main differences between TCP and UDP?', 360),
  ('Explain async/await in JavaScript with a simple example', 480),
  ('How does garbage collection work in Python?', 600);