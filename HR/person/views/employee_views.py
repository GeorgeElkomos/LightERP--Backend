from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from HR.person.models import Employee, Person, PersonType
from HR.person.services.employee_service import EmployeeService
from HR.person.serializers.employee_serializers import EmployeeSerializer, EmployeeCreateSerializer, EmployeeUpdateSerializer

@api_view(['GET', 'POST'])
@require_page_action('hr_person_employee')
@auto_paginate
def employee_list(request):
    """
    List employees or create new employee.
    
    GET /person/employees/
    - Filters: as_of_date, status, search, organization_id, position_id, employee_type_id
    
    POST /person/employees/
    - Create new employee (hire direct)
    """
    if request.method == 'GET':
        filters = {
            'as_of_date': request.query_params.get('as_of_date', 'ALL'),
            'search': request.query_params.get('search'),
            'organization_id': request.query_params.get('organization_id'),
            'position_id': request.query_params.get('position_id'),
            'employee_type_id': request.query_params.get('employee_type_id'),
            'person_id': request.query_params.get('person_id')
        }
        
        employees = EmployeeService.list_employees(filters)
            
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        serializer = EmployeeCreateSerializer(data=request.data)
        if serializer.is_valid():
            dto = serializer.to_dto()
            
            # Prepare employee data
            employee_type = get_object_or_404(PersonType, pk=dto.employee_type_id)
            
            employee_data = {
                'employee_type': employee_type,
                'employee_number': dto.employee_number,
            }
            
            try:
                if dto.person_id:
                    # Hire existing person
                    person = get_object_or_404(Person, pk=dto.person_id)
                    employee = EmployeeService.hire_direct(
                        person_data={}, 
                        employee_data=employee_data, 
                        effective_start_date=dto.effective_start_date,
                        hire_date=dto.hire_date,
                        person=person
                    )
                else:
                    # Create new person and hire
                    person_data = {
                        'first_name': dto.first_name,
                        'last_name': dto.last_name,
                        'email_address': dto.email_address,
                        'date_of_birth': dto.date_of_birth,
                        'gender': dto.gender,
                        'nationality': dto.nationality,
                        'marital_status': dto.marital_status,
                        'middle_name': dto.middle_name or '',
                        'national_id': dto.national_id or None,
                        'title': dto.title or '',
                        'first_name_arabic': dto.first_name_arabic or '',
                        'middle_name_arabic': dto.middle_name_arabic or '',
                        'last_name_arabic': dto.last_name_arabic or '',
                        'religion': dto.religion or '',
                        'blood_type': dto.blood_type or '',
                    }
                    employee = EmployeeService.hire_direct(
                        person_data=person_data,
                        employee_data=employee_data,
                        effective_start_date=dto.effective_start_date,
                        hire_date=dto.hire_date
                    )
                
                return Response(EmployeeSerializer(employee).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_person_employee')
def employee_detail(request, pk):
    """
    Retrieve, update or deactivate employee.
    """
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'GET':
        serializer = EmployeeSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['employee_id'] = pk
        
        serializer = EmployeeUpdateSerializer(instance=employee, data=data)
        if serializer.is_valid():
             try:
                 dto = serializer.to_dto()
                 updated_employee = EmployeeService.update(request.user, dto)
                 return Response(EmployeeSerializer(updated_employee).data, status=status.HTTP_200_OK)
             except Exception as e:
                 return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
             
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        try:
            EmployeeService.terminate(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
