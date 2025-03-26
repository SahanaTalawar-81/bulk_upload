import React, { useState } from 'react';
import axios from 'axios';
import './style.css'; // Import your custom CSS file

function App() {
  const [questionPaper, setQuestionPaper] = useState(null);
  const [answerSheet, setAnswerSheet] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false); // State for loader
  const [showNotification, setShowNotification] = useState(false); // State for notification

  const handleFileChange = (e, setFile) => {
    setFile(e.target.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!questionPaper || !answerSheet) {
      setError('Please upload both question paper and answer sheet.');
      return;
    }

    setIsLoading(true); // Show loader
    setError('');
    setShowNotification(false); // Hide notification

    const formData = new FormData();
    formData.append('questionPaper', questionPaper);
    formData.append('answerSheet', answerSheet);

    try {
      const response = await axios.post('http://localhost:5000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        responseType: 'blob', // Ensure the response is treated as a binary file
      });

      // Create a URL for the blob
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'final_output.xlsx'); // Set the file name
      document.body.appendChild(link);
      link.click(); // Trigger the download
      link.remove(); // Clean up

      setShowNotification(true); // Show notification
    } catch (err) {
      setError('Failed to process files. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false); // Hide loader
    }
  };

  return (
    <div className="container">
      <h1>Question Paper Processor</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="questionPaper">Upload Question Paper:</label>
          <input
            type="file"
            id="questionPaper"
            onChange={(e) => handleFileChange(e, setQuestionPaper)}
          />
        </div>
        <div>
          <label htmlFor="answerSheet">Upload Answer Sheet:</label>
          <input
            type="file"
            id="answerSheet"
            onChange={(e) => handleFileChange(e, setAnswerSheet)}
          />
        </div>
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Processing...' : 'Process Files'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {isLoading && (
        <div id="loading">
          <div className="loader"></div>
          <p>Take a long breath and chill, your file is getting processed, Content Team. 🚀</p>
        </div>
      )}

      {showNotification && (
        <div className="success">🎉  File downloaded successfully! 🎉 </div>
      )}

      <footer>
      &copy;2025 <a href="Upschool" target="_blank" rel="noopener noreferrer"> UpSchool </a> All rights reserved
      </footer>
    </div>
  );
}

export default App;