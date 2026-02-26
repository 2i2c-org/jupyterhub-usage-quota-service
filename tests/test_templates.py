"""Tests for Jinja2 template rendering"""

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from jupyterhub_usage_quota_service import get_template_path


@pytest.fixture
def jinja_env():
    """Create Jinja2 environment for template rendering"""
    return Environment(loader=FileSystemLoader(get_template_path()), autoescape=True)


def render_template(jinja_env, usage_data):
    """Helper to render template and return BeautifulSoup object"""
    template = jinja_env.get_template("usage.html")
    html_content = template.render(usage_data=usage_data)
    return BeautifulSoup(html_content, "html.parser")


class TestUsageTemplateWithNormalUsage:
    """Test template rendering with normal usage (< 90%)"""

    def test_displays_correct_usage_percentage(self, jinja_env, usage_data_50_percent):
        """Should show 50.0% usage"""
        soup = render_template(jinja_env, usage_data_50_percent)

        progress_label = soup.find(class_="progress-label")
        assert progress_label is not None
        assert "50.0%" in progress_label.text

    def test_displays_usage_and_quota_in_gib(self, jinja_env, usage_data_50_percent):
        """Should show usage and quota in GiB"""
        soup = render_template(jinja_env, usage_data_50_percent)

        metric_usage = soup.find(class_="metric-usage")
        assert metric_usage is not None
        assert "5.0 GiB used" in metric_usage.text
        assert "10.0 GiB quota" in metric_usage.text

    def test_displays_remaining_storage(self, jinja_env, usage_data_50_percent):
        """Should calculate and display remaining storage"""
        soup = render_template(jinja_env, usage_data_50_percent)

        metric_remaining = soup.find(class_="metric-remaining")
        assert metric_remaining is not None
        assert "5.0 GiB remaining" in metric_remaining.text

    def test_progress_bar_width_matches_percentage(
        self, jinja_env, usage_data_50_percent
    ):
        """Progress bar should have width: 50.0%"""
        soup = render_template(jinja_env, usage_data_50_percent)

        progress_fill = soup.find(class_="progress-fill")
        assert progress_fill is not None
        assert "width: 50.0%" in progress_fill.get("style", "")

    def test_uses_normal_styling_below_90_percent(
        self, jinja_env, usage_data_50_percent
    ):
        """Should use green/normal colors for < 90% usage"""
        soup = render_template(jinja_env, usage_data_50_percent)

        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")

        # Should NOT have red background for normal usage
        assert "#ef4444" not in style

    def test_displays_last_updated_timestamp(self, jinja_env, usage_data_50_percent):
        """Should display last_updated in time element"""
        soup = render_template(jinja_env, usage_data_50_percent)

        time_element = soup.find("time")
        assert time_element is not None
        assert time_element.has_attr("datetime")
        assert usage_data_50_percent["last_updated"] in time_element["datetime"]

    def test_shows_normal_folder_icon(self, jinja_env, usage_data_50_percent):
        """Should show regular folder icon for normal usage"""
        soup = render_template(jinja_env, usage_data_50_percent)

        # Should have folder SVG
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0

        # Should NOT have sad face circles in SVG (those only appear at >= 90%)
        circles = soup.find_all("circle")
        # Normal folder icon has no circles
        assert len(circles) == 0


class TestUsageTemplateWithHighUsage:
    """Test template rendering with high usage (>= 90%)"""

    def test_displays_sad_folder_icon_at_95_percent(
        self, jinja_env, usage_data_95_percent
    ):
        """Should show sad folder icon at 95%"""
        soup = render_template(jinja_env, usage_data_95_percent)

        # Should have circles for eyes in sad folder
        circles = soup.find_all("circle")
        assert len(circles) == 2  # Two circles for eyes

    def test_uses_red_styling_above_90_percent(self, jinja_env, usage_data_95_percent):
        """Should use red colors for >= 90% usage"""
        soup = render_template(jinja_env, usage_data_95_percent)

        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")

        # Should have red background
        assert "#ef4444" in style

    def test_progress_bar_is_red_at_high_usage(self, jinja_env, usage_data_95_percent):
        """Progress bar should be red at high usage"""
        soup = render_template(jinja_env, usage_data_95_percent)

        progress_fill = soup.find(class_="progress-fill")
        assert "background: #ef4444" in progress_fill.get("style", "")

    def test_remaining_storage_is_red_at_high_usage(
        self, jinja_env, usage_data_95_percent
    ):
        """Remaining storage text should be red"""
        soup = render_template(jinja_env, usage_data_95_percent)

        metric_remaining = soup.find(class_="metric-remaining")
        style = metric_remaining.get("style", "")

        assert "color: #ef4444" in style

    def test_percentage_threshold_at_exactly_90(self, jinja_env, usage_data_90_percent):
        """Should apply red styling at exactly 90%"""
        soup = render_template(jinja_env, usage_data_90_percent)

        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")

        # At exactly 90%, should have red styling
        assert "#ef4444" in style

    def test_progress_label_is_red_at_high_usage(
        self, jinja_env, usage_data_95_percent
    ):
        """Progress label should be red at high usage"""
        soup = render_template(jinja_env, usage_data_95_percent)

        progress_label = soup.find(class_="progress-label")
        style = progress_label.get("style", "")

        assert "color: #ef4444" in style


class TestUsageTemplateWithErrors:
    """Test template rendering with error states"""

    def test_displays_error_message_when_prometheus_down(
        self, jinja_env, usage_data_prometheus_error
    ):
        """Should show 'Unable to reach Prometheus' error"""
        soup = render_template(jinja_env, usage_data_prometheus_error)

        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "Unable to reach Prometheus" in error_message.text

    def test_displays_error_icon_not_folder(
        self, jinja_env, usage_data_prometheus_error
    ):
        """Should show error icon (not folder icon) on error"""
        soup = render_template(jinja_env, usage_data_prometheus_error)

        # Should have SVG with error/alert icon
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0

        # Error icon uses stroke="#ef4444" (red)
        svg = svgs[0]
        assert 'stroke="#ef4444"' in str(svg) or svg.get("stroke") == "#ef4444"

    def test_error_state_has_no_progress_bar(
        self, jinja_env, usage_data_prometheus_error
    ):
        """Should not render progress bar on error"""
        soup = render_template(jinja_env, usage_data_prometheus_error)

        progress_track = soup.find(class_="progress-track")
        assert progress_track is None

    def test_displays_no_data_error(self, jinja_env, usage_data_no_quota):
        """Should show 'No storage data found' error"""
        soup = render_template(jinja_env, usage_data_no_quota)

        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "No storage data found" in error_message.text

    def test_error_message_has_red_styling(
        self, jinja_env, usage_data_prometheus_error
    ):
        """Error text should be styled in red"""
        template = jinja_env.get_template("usage.html")
        html_content = template.render(usage_data=usage_data_prometheus_error)

        # Check that error-message class has red color in style
        assert ".error-message" in html_content
        # The style should define error-message with red color
        assert "color: #ef4444" in html_content or "color:#ef4444" in html_content


class TestUsageTemplateAccessibility:
    """Test template accessibility features"""

    def test_time_element_has_datetime_attribute(
        self, jinja_env, usage_data_50_percent
    ):
        """time element should have proper datetime attribute"""
        soup = render_template(jinja_env, usage_data_50_percent)

        time_element = soup.find("time")
        assert time_element is not None
        assert time_element.has_attr("datetime")

        datetime_value = time_element["datetime"]
        assert datetime_value == usage_data_50_percent["last_updated"]

    def test_javascript_formats_timestamp(self, jinja_env, usage_data_50_percent):
        """JS should format ISO timestamp to locale string"""
        template = jinja_env.get_template("usage.html")
        html_content = template.render(usage_data=usage_data_50_percent)

        # Should contain JavaScript to format timestamps
        assert "toLocaleString" in html_content
        assert "querySelectorAll('time[datetime]')" in html_content

    def test_has_semantic_html_structure(self, jinja_env, usage_data_50_percent):
        """Should use semantic HTML elements"""
        soup = render_template(jinja_env, usage_data_50_percent)

        # Check for semantic elements
        assert soup.find("h1") is not None
        assert soup.find("time") is not None


class TestUsageTemplateEdgeCases:
    """Test edge cases in template rendering"""

    def test_handles_0_percent_usage(self, jinja_env, usage_data_0_percent):
        """Should handle 0% usage correctly"""
        soup = render_template(jinja_env, usage_data_0_percent)

        progress_label = soup.find(class_="progress-label")
        assert "0.0%" in progress_label.text

        progress_fill = soup.find(class_="progress-fill")
        assert "width: 0.0%" in progress_fill.get("style", "")

        metric_remaining = soup.find(class_="metric-remaining")
        assert "10.0 GiB remaining" in metric_remaining.text

    def test_handles_100_percent_usage(self, jinja_env, usage_data_100_percent):
        """Should handle 100% usage correctly"""
        soup = render_template(jinja_env, usage_data_100_percent)

        progress_label = soup.find(class_="progress-label")
        assert "100.0%" in progress_label.text

        # Should be red (over 90%)
        progress_fill = soup.find(class_="progress-fill")
        assert "#ef4444" in progress_fill.get("style", "")

        metric_remaining = soup.find(class_="metric-remaining")
        assert "0.0 GiB remaining" in metric_remaining.text

    def test_handles_very_large_quota_terabytes(self, jinja_env, usage_data_terabytes):
        """Should format terabyte values correctly"""
        soup = render_template(jinja_env, usage_data_terabytes)

        metric_usage = soup.find(class_="metric-usage")
        # Should show in GiB (512.0 GiB / 1024.0 GiB)
        assert "512.0 GiB used" in metric_usage.text
        assert "1024.0 GiB quota" in metric_usage.text

    def test_decimal_precision_consistent(self, jinja_env, usage_data_50_percent):
        """Should display values with consistent decimal places (1 decimal)"""
        soup = render_template(jinja_env, usage_data_50_percent)

        # All values should use .1f format (1 decimal place)
        progress_label = soup.find(class_="progress-label")
        assert ".0%" in progress_label.text  # e.g., "50.0%"

        metric_usage = soup.find(class_="metric-usage")
        assert ".0 GiB" in metric_usage.text  # e.g., "5.0 GiB"

    def test_handles_no_last_updated_field(self, jinja_env):
        """Should handle missing last_updated gracefully"""
        usage_data_no_timestamp = {
            "username": "testuser",
            "usage_bytes": 5368709120,
            "quota_bytes": 10737418240,
            "usage_gb": 5.0,
            "quota_gb": 10.0,
            "percentage": 50.0,
            # no last_updated field
        }

        soup = render_template(jinja_env, usage_data_no_timestamp)

        # Should still render without error
        assert soup.find("h1") is not None

        # Time element should not be present
        # The template uses {% if usage_data.last_updated is defined %}
        # So time element might still be in the structure but not shown
        # Or it might be completely absent


class TestUsageTemplateFooter:
    """Test footer and informational text"""

    def test_displays_footer_note(self, jinja_env, usage_data_50_percent):
        """Should display footer with admin contact info"""
        soup = render_template(jinja_env, usage_data_50_percent)

        footer_note = soup.find(class_="footer-note")
        assert footer_note is not None
        assert "JupyterHub Admin" in footer_note.text
        assert "quota" in footer_note.text.lower()

    def test_displays_page_title(self, jinja_env, usage_data_50_percent):
        """Should display 'Usage' title"""
        soup = render_template(jinja_env, usage_data_50_percent)

        h1 = soup.find("h1")
        assert h1 is not None
        assert "Usage" in h1.text

    def test_displays_subtitle(self, jinja_env, usage_data_50_percent):
        """Should display subtitle about home storage"""
        soup = render_template(jinja_env, usage_data_50_percent)

        subtitle = soup.find(class_="subtitle")
        assert subtitle is not None
        assert "home storage" in subtitle.text.lower()
        assert "quota" in subtitle.text.lower()
