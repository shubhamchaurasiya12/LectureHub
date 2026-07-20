// D:\iitm_scheduler\templates\components\subject_dropdown.js
// Reusable Subject Dropdown JavaScript

class SubjectDropdown {
  constructor(options = {}) {
    this.selectId = options.selectId || 'subject-select';
    this.customInputId = options.customInputId || 'custom-subject-input';
    this.customWrapperId = options.customWrapperId || 'custom-subject-wrapper';
    this.calendarUrlId = options.calendarUrlId || 'calendar-url';
    this.urlStatusId = options.urlStatusId || 'url-status';
    this.urlFeedbackId = options.urlFeedbackId || 'url-feedback';
    this.fetchUrlEndpoint = options.fetchUrlEndpoint || '/get_subject_url/';
    
    this.select = document.getElementById(this.selectId);
    this.customInput = document.getElementById(this.customInputId);
    this.customWrapper = document.getElementById(this.customWrapperId);
    this.calendarUrl = document.getElementById(this.calendarUrlId);
    this.urlStatus = document.getElementById(this.urlStatusId);
    this.urlFeedback = document.getElementById(this.urlFeedbackId);
    
    this.originalPlaceholder = this.calendarUrl ? this.calendarUrl.placeholder : '';
    
    this.init();
  }
  
  init() {
    if (!this.select) return;
    
    // Bind event listeners
    this.select.addEventListener('change', this.handleSelectChange.bind(this));
    
    // Handle custom subject input
    if (this.customInput) {
      this.customInput.addEventListener('input', this.handleCustomInput.bind(this));
      this.customInput.addEventListener('blur', this.handleCustomBlur.bind(this));
    }
    
    // Trigger initial change if there's a value
    if (this.select.value) {
      this.select.dispatchEvent(new Event('change'));
    }
    
    console.log('SubjectDropdown initialized');
  }
  
  async handleSelectChange(event) {
    const selectedOption = this.select.options[this.select.selectedIndex];
    const subjectName = this.select.value;
    const dataUrl = selectedOption ? selectedOption.getAttribute('data-url') : null;
    
    // Clear previous status
    this.clearStatus();
    
    // Handle custom subject option
    if (subjectName === '__custom__') {
      this.showCustomInput();
      return;
    } else {
      this.hideCustomInput();
    }
    
    if (!subjectName) {
      this.resetCalendarUrl();
      return;
    }
    
    // Check if URL is stored in data attribute
    if (dataUrl && dataUrl.trim() !== '') {
      this.fillCalendarUrl(dataUrl, 'auto-filled from database');
      return;
    }
    
    // If no URL in data attribute, try fetching from server
    this.showLoading();
    
    try {
      const result = await this.fetchCalendarUrl(subjectName);
      
      if (result && result.found && result.calendar_url) {
        this.fillCalendarUrl(result.calendar_url, 'auto-filled');
        // Update the data attribute for future use
        if (selectedOption) {
          selectedOption.setAttribute('data-url', result.calendar_url);
        }
      } else {
        this.showManualEntryRequired();
      }
    } catch (error) {
      console.error('Error fetching calendar URL:', error);
      this.showManualEntryRequired();
    }
  }
  
  async fetchCalendarUrl(subjectName) {
    if (!subjectName) return null;
    
    try {
      const response = await fetch(`${this.fetchUrlEndpoint}${encodeURIComponent(subjectName)}`);
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error fetching calendar URL:', error);
      return null;
    }
  }
  
  fillCalendarUrl(url, source = 'auto-filled') {
    if (!this.calendarUrl) return;
    
    this.calendarUrl.value = url;
    this.calendarUrl.placeholder = this.originalPlaceholder;
    this.calendarUrl.disabled = false;
    this.calendarUrl.style.borderColor = 'var(--green)';
    
    if (this.urlStatus) {
      this.urlStatus.innerHTML = '✅';
    }
    
    if (this.urlFeedback) {
      this.urlFeedback.innerHTML = `<span style="color: var(--green);">✓ Calendar URL ${source}</span>`;
    }
  }
  
  showManualEntryRequired() {
    if (!this.calendarUrl) return;
    
    this.calendarUrl.value = '';
    this.calendarUrl.placeholder = 'Paste the Google Calendar link here';
    this.calendarUrl.disabled = false;
    this.calendarUrl.style.borderColor = 'var(--amber)';
    
    if (this.urlStatus) {
      this.urlStatus.innerHTML = '⚠️';
    }
    
    if (this.urlFeedback) {
      this.urlFeedback.innerHTML = '<span style="color: var(--amber);">⚠ No stored calendar URL. Please paste it manually.</span>';
    }
  }
  
  showCustomInput() {
    if (this.customWrapper) {
      this.customWrapper.classList.add('visible');
    }
    if (this.customInput) {
      this.customInput.required = true;
      setTimeout(() => this.customInput.focus(), 100);
    }
    
    if (this.calendarUrl) {
      this.calendarUrl.value = '';
      this.calendarUrl.placeholder = 'Paste the Google Calendar link here';
      this.calendarUrl.disabled = false;
    }
    
    if (this.urlStatus) {
      this.urlStatus.innerHTML = '✏️';
    }
    
    if (this.urlFeedback) {
      this.urlFeedback.innerHTML = '<span style="color: var(--accent);">Enter your custom subject name above, then paste the calendar link.</span>';
    }
  }
  
  hideCustomInput() {
    if (this.customWrapper) {
      this.customWrapper.classList.remove('visible');
    }
    if (this.customInput) {
      this.customInput.required = false;
      this.customInput.value = '';
      this.customInput.style.borderColor = '';
    }
  }
  
  handleCustomInput(event) {
    const value = event.target.value.trim();
    if (value) {
      event.target.style.borderColor = 'var(--green)';
    } else {
      event.target.style.borderColor = '';
    }
  }
  
  handleCustomBlur(event) {
    const value = event.target.value.trim();
    if (!value && this.select.value === '__custom__') {
      event.target.style.borderColor = 'var(--red)';
    }
  }
  
  showLoading() {
    if (this.urlStatus) {
      this.urlStatus.innerHTML = '<span class="url-loading"></span>';
    }
    if (this.urlFeedback) {
      this.urlFeedback.textContent = 'Checking for calendar URL...';
    }
  }
  
  clearStatus() {
    if (this.urlStatus) {
      this.urlStatus.innerHTML = '';
    }
    if (this.urlFeedback) {
      this.urlFeedback.textContent = '';
    }
    if (this.calendarUrl) {
      this.calendarUrl.style.borderColor = '';
    }
  }
  
  resetCalendarUrl() {
    if (this.calendarUrl) {
      this.calendarUrl.value = '';
      this.calendarUrl.placeholder = this.originalPlaceholder;
      this.calendarUrl.disabled = false;
      this.calendarUrl.style.borderColor = '';
    }
  }
  
  // Static method to initialize multiple dropdowns
  static initAll(selectors = {}) {
    const defaults = {
      selectId: 'subject-select',
      customInputId: 'custom-subject-input',
      customWrapperId: 'custom-subject-wrapper',
      calendarUrlId: 'calendar-url',
      urlStatusId: 'url-status',
      urlFeedbackId: 'url-feedback'
    };
    
    const config = { ...defaults, ...selectors };
    return new SubjectDropdown(config);
  }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SubjectDropdown;
}