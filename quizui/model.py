"""Desktop sessions and recoverable answer drafts, independent of Tk widgets."""
import json
from pathlib import Path
from quizcore.validation import AppError


class DesktopSession:
    def __init__(self, service):
        self.service = service
        self.token = None

    def login(self, username, password):
        result = self.service.auth.login({'username': username, 'password': password})
        self.token = result['token']
        return self.actor

    @property
    def actor(self):
        actor = self.service.auth.session(self.token)
        if actor is None:
            self.token = None
            raise AppError('Your session ended. Please sign in again.', 401)
        return actor

    def logout(self):
        if self.token:
            actor = self.service.auth.session(self.token)
            self.service.auth.logout(self.token, actor)
        self.token = None


class AnswerDrafts:
    """Atomic, per-user recovery files. A draft never bypasses the quiz deadline."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, user_id, attempt_id):
        return self.directory / f'{int(user_id)}_{int(attempt_id)}.json'

    def write(self, user_id, attempt):
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.path(user_id, attempt['id'])
        temporary = target.with_suffix('.tmp')
        payload = {'version': attempt['version'], 'answers': attempt['answers']}
        temporary.write_text(json.dumps(payload), encoding='utf-8')
        temporary.replace(target)

    def read(self, user_id, attempt):
        target = self.path(user_id, attempt['id'])
        try:
            value = json.loads(target.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            raise AppError('The local answer draft cannot be read. Your saved database answers are still available.') from error
        allowed = {str(q['id']) for q in attempt['questions']}
        if (not isinstance(value, dict) or type(value.get('version')) is not int
                or not isinstance(value.get('answers'), dict)
                or any(k not in allowed or type(v) is not int or not 0 <= v <= 3
                       for k, v in value['answers'].items())):
            raise AppError('The local answer draft is invalid. Use the saved database answers.')
        return value

    def clear(self, user_id, attempt_id):
        self.path(user_id, attempt_id).unlink(missing_ok=True)


class ExamSession:
    def __init__(self, session, attempt_id):
        self.session = session
        self.service = session.service
        self.drafts = AnswerDrafts(self.service.config.data_dir / 'answer_drafts')
        self.attempt = self.service.attempts.get(session.actor, attempt_id)
        self.user_id = session.actor['id']
        self.dirty = False
        self.draft_error = ''

    def recover(self):
        if self.attempt['submitted_at'] is not None:
            self.drafts.clear(self.user_id, self.attempt['id'])
            return False
        draft = self.drafts.read(self.user_id, self.attempt)
        if draft is None:
            return False
        if draft['version'] != self.attempt['version']:
            if draft['answers'] == self.attempt['answers']:
                self.drafts.clear(self.user_id, self.attempt['id'])
                return False
            raise AppError('The saved attempt changed after this local draft. Use Reload saved answers to avoid overwriting newer answers.', 409)
        self.attempt['answers'] = draft['answers']
        self.dirty = True
        return True

    def choose(self, question_id, option):
        allowed = {q['id'] for q in self.attempt['questions']}
        if question_id not in allowed or type(option) is not int or not 0 <= option <= 3:
            raise AppError('Choose one of the four answers for this question.')
        if self.attempt['submitted_at'] is not None:
            raise AppError('This attempt has already been submitted.')
        self.attempt['answers'][str(question_id)] = option
        self.dirty = True
        # A failed local-draft write must not prevent trying the primary save.
        self.draft_error = ''
        try:
            self.drafts.write(self.user_id, self.attempt)
        except OSError:
            self.draft_error = 'Local draft could not be written. Keep the app open until the database save succeeds.'
        return self.save()

    def save(self, submit=False):
        if not self.dirty and not submit:
            return self.attempt
        result = self.service.attempts.save(self.session.actor, self.attempt['id'],
            {'version': self.attempt['version'], 'answers': self.attempt['answers']}, submit)
        self.attempt = result
        self.dirty = False
        try:
            self.drafts.clear(self.user_id, result['id'])
        except OSError:
            self.draft_error = 'Answers are saved; an old local draft could not be removed.'
        return result

    def reload(self):
        self.attempt = self.service.attempts.get(self.session.actor, self.attempt['id'])
        self.dirty = False
        self.drafts.clear(self.user_id, self.attempt['id'])
        return self.attempt
