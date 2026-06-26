from backend.investigations.question_interpreter import QuestionInterpreter

questions = [
    "Why did Firman lose to Champion?",
    "Compare Firman vs Honda for quiet generators",
    "Why is Champion winning for dual fuel?",
    "How is Firman doing?",
]

interpreter = QuestionInterpreter()

for question in questions:
    print(question)
    print(interpreter.interpret(question))
    print("-" * 50)