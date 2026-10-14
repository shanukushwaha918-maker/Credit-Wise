from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Category values are exactly those the notebook's encoders were fitted on.
EmploymentStatus = Literal["Contract", "Salaried", "Self-employed", "Unemployed"]
MaritalStatus = Literal["Married", "Single"]
LoanPurpose = Literal["Business", "Car", "Education", "Home", "Personal"]
PropertyArea = Literal["Rural", "Semiurban", "Urban"]
EducationLevel = Literal["Graduate", "Not Graduate"]
Gender = Literal["Female", "Male"]
EmployerCategory = Literal["Business", "Government", "MNC", "Private", "Unemployed"]
ModelName = Literal["naive_bayes", "logistic_regression", "knn"]


class Applicant(BaseModel):
    """One loan application. Field names match the dataset columns."""
    model_config = ConfigDict(extra="forbid")

    Applicant_Income: float = Field(ge=0, le=10_000_000)
    Coapplicant_Income: float = Field(ge=0, le=10_000_000)
    Employment_Status: EmploymentStatus
    Age: float = Field(ge=18, le=100)
    Marital_Status: MaritalStatus
    Dependents: int = Field(ge=0, le=20)
    Credit_Score: float = Field(ge=300, le=900)
    Existing_Loans: int = Field(ge=0, le=50)
    DTI_Ratio: float = Field(ge=0, le=1)
    Savings: float = Field(ge=0, le=100_000_000)
    Collateral_Value: float = Field(ge=0, le=100_000_000)
    Loan_Amount: float = Field(gt=0, le=100_000_000)
    Loan_Term: int = Field(ge=1, le=480, description="months")
    Loan_Purpose: LoanPurpose
    Property_Area: PropertyArea
    Education_Level: EducationLevel
    Gender: Gender
    Employer_Category: EmployerCategory


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    applicant: Applicant
    model: Optional[ModelName] = None
    save: bool = True
